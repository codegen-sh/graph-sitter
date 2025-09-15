#!/usr/bin/env python3
"""
MCP Server for KuzuDB integration with graph-sitter.

This server exposes KuzuDB graph capabilities through the Model Context Protocol,
providing tools for querying, analysis, and monitoring of code graphs.
"""

import argparse
import asyncio
import atexit
import json
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to Python path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import colorlog
from mcp.server.fastmcp import FastMCP

# Import graph-sitter components
from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.kuzu_map.sync import KuzuSync
from graph_sitter.extensions.kuzu_map.monitor import CodeGraphAnalyzer

# Initialize FastMCP server
mcp = FastMCP("graph-sitter-kuzu")

@dataclass
class InitializationState:
    """Track initialization progress and state."""
    is_complete: bool = False
    is_running: bool = False
    progress_message: str = "Not started"
    files_processed: int = 0
    total_files: int = 0
    error: Optional[str] = None
    start_time: Optional[float] = None

    @property
    def progress_percentage(self) -> int:
        if self.total_files == 0:
            return 0
        return min(100, int((self.files_processed / self.total_files) * 100))

    @property
    def elapsed_time(self) -> float:
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

# Global state
codebase: Optional[Codebase] = None
kuzu_sync: Optional[KuzuSync] = None
analyzer: Optional[CodeGraphAnalyzer] = None
init_state = InitializationState()
init_lock = threading.Lock()

logger = logging.getLogger(__name__)


def cleanup_server() -> None:
    """Clean up server resources."""
    global kuzu_sync

    logger.info("Cleaning up MCP server resources...")

    if kuzu_sync:
        try:
            kuzu_sync.close()
            logger.info("Database connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")

    logger.info("MCP server cleanup completed")


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_server()
    sys.exit(0)


def _error_response(error: Exception) -> Dict[str, Any]:
    """Create MCP-compliant error response."""
    return {
        "success": False,
        "error": str(error),
        "error_type": type(error).__name__
    }


def _success_response(data: Any, execution_time_ms: Optional[float] = None) -> Dict[str, Any]:
    """Create MCP-compliant success response."""
    response = {
        "success": True,
        "data": data
    }
    if execution_time_ms is not None:
        response["execution_time_ms"] = execution_time_ms
    return response


def _initializing_response() -> Dict[str, Any]:
    """Create MCP-compliant initialization status response."""
    with init_lock:
        return {
            "success": True,
            "status": "initializing",
            "data": {
                "progress_percentage": init_state.progress_percentage,
                "progress_message": init_state.progress_message,
                "files_processed": init_state.files_processed,
                "total_files": init_state.total_files,
                "elapsed_time_seconds": round(init_state.elapsed_time, 1),
                "is_complete": init_state.is_complete,
                "error": init_state.error
            }
        }


def _update_progress(message: str, files_processed: int = 0, total_files: int = 0) -> None:
    """Update initialization progress thread-safely."""
    with init_lock:
        init_state.progress_message = message
        init_state.files_processed = files_processed
        init_state.total_files = total_files
        logger.info(f"Initialization: {message} ({files_processed}/{total_files})")


def _background_initialization(project_path: str, db_path: Optional[str], enable_monitoring: bool) -> None:
    """Background thread function for codebase initialization."""
    global codebase, kuzu_sync, analyzer

    try:
        with init_lock:
            init_state.is_running = True
            init_state.start_time = time.time()
            init_state.error = None

        _update_progress("Initializing codebase...")

        # Initialize codebase
        codebase = Codebase(
            repo_path=project_path,
            language="python"  # Default to Python, could be made configurable
        )

        # Get file count for progress tracking
        file_count = len(codebase.files)
        _update_progress("Scanning files...", 0, file_count)

        # Initialize KuzuDB connection
        _update_progress("Connecting to KuzuDB...", 0, file_count)
        kuzu_sync = KuzuSync(
            codebase=codebase,
            db_path=db_path or "./code_graph.kuzu"
        )

        # Perform initial sync with progress updates
        _update_progress("Synchronizing with database...", 0, file_count)

        # We'll track sync progress by monitoring the codebase state
        # Since KuzuSync doesn't provide built-in progress tracking,
        # we'll estimate based on processing time
        sync_start = time.time()
        kuzu_sync.sync_full()

        # Estimate completion based on processing
        _update_progress("Sync completed, finalizing...", file_count, file_count)

        # Initialize analyzer if monitoring is enabled
        if enable_monitoring:
            _update_progress("Initializing code analyzer...", file_count, file_count)
            analyzer = CodeGraphAnalyzer(kuzu_sync)

        # Mark as complete
        with init_lock:
            init_state.is_complete = True
            init_state.is_running = False
            init_state.progress_message = "Initialization complete"

        logger.info(f"Background initialization completed in {init_state.elapsed_time:.1f} seconds")

    except Exception as e:
        error_msg = f"Initialization failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        with init_lock:
            init_state.error = error_msg
            init_state.is_running = False
            init_state.progress_message = "Initialization failed"


def start_background_initialization(project_path: str, db_path: Optional[str], enable_monitoring: bool) -> None:
    """Start background initialization if not already running."""
    with init_lock:
        if init_state.is_running or init_state.is_complete:
            return

    # Start background thread
    init_thread = threading.Thread(
        target=_background_initialization,
        args=(project_path, db_path, enable_monitoring),
        daemon=True
    )
    init_thread.start()
    logger.info("Started background initialization thread")


# MCP Tools Implementation

@mcp.tool()
async def query(cypher_query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Cypher queries against the KuzuDB graph database.

    Args:
        cypher_query: The Cypher query to execute
        parameters: Optional query parameters

    Returns:
        Query results with execution metrics or error information
    """
    # Check initialization state first
    if not init_state.is_complete:
        return _initializing_response()

    if not kuzu_sync:
        return _error_response(RuntimeError("KuzuDB not initialized"))

    try:
        start_time = time.time()

        result = await asyncio.get_event_loop().run_in_executor(
            None, kuzu_sync.query, cypher_query, parameters or {}
        )

        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Convert result to DataFrame and then to records
        if result and hasattr(result, 'get_as_df'):
            df = result.get_as_df()
            data = {
                "rows": df.to_dict('records') if not df.empty else [],
                "row_count": len(df),
                "columns": list(df.columns) if not df.empty else []
            }
        else:
            data = {
                "rows": [],
                "row_count": 0,
                "columns": []
            }

        return _success_response(data, execution_time)

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return _error_response(e)


@mcp.tool()
async def get_schema() -> Dict[str, Any]:
    """
    Retrieve complete database schema including graph-sitter specific tables.

    Returns:
        Schema information with node tables, relationship tables, and properties
    """
    # Check initialization state first
    if not init_state.is_complete:
        return _initializing_response()

    if not kuzu_sync:
        return _error_response(RuntimeError("KuzuDB not initialized"))

    try:
        # Get table information
        tables_query = "CALL SHOW_TABLES() RETURN *"
        tables_result = await asyncio.get_event_loop().run_in_executor(
            None, kuzu_sync.query, tables_query
        )

        schema_info = {
            "node_tables": [
                "File", "Function", "Class", "Import",
                "Symbol", "Assignment", "Interface", "TypeAlias",
                "Parameter", "CodeBlock"
            ],
            "relationship_tables": [
                "CONTAINS_FUNCTION", "CONTAINS_CLASS", "CONTAINS_IMPORT",
                "CLASS_METHOD", "FUNCTION_CALLS", "IMPORTS", "INHERITS",
                "DECLARES_SYMBOL", "CLASS_FIELD", "ASSIGNS_TO",
                "ASSIGNMENT_IN_FUNCTION", "IMPLEMENTS", "INTERFACE_METHOD",
                "USES_TYPE", "HAS_PARAMETER", "CONTAINS_BLOCK", "NESTED_BLOCK"
            ],
            "graph_sitter_specific": {
                "entities": ["File", "Function", "Class", "Symbol", "Assignment", "Interface", "TypeAlias", "Parameter", "CodeBlock"],
                "analysis_capabilities": ["complexity", "unused_detection", "parameter_analysis", "code_block_nesting"]
            },
            "raw_tables": tables_result.get_as_df().to_dict('records') if tables_result and hasattr(tables_result, 'get_as_df') else []
        }

        return _success_response(schema_info)

    except Exception as e:
        logger.error(f"Schema retrieval failed: {e}")
        return _error_response(e)


@mcp.tool()
async def get_codebase_overview() -> Dict[str, Any]:
    """
    Get high-level statistics about the synchronized codebase.

    Returns:
        Entity counts, file statistics, complexity metrics
    """
    # Check initialization state first
    if not init_state.is_complete:
        return _initializing_response()

    if not analyzer:
        return _error_response(RuntimeError("CodeGraphAnalyzer not initialized"))

    try:
        overview_result = await asyncio.get_event_loop().run_in_executor(
            None, analyzer.get_codebase_overview
        )

        if overview_result and hasattr(overview_result, 'get_next') and overview_result.has_next():
            row = overview_result.get_next()
            overview_data = {
                "total_files": row[0] if len(row) > 0 else 0,
                "total_functions": row[1] if len(row) > 1 else 0,
                "total_classes": row[2] if len(row) > 2 else 0,
                "total_symbols": row[3] if len(row) > 3 else 0,
                "total_assignments": row[4] if len(row) > 4 else 0,
                "total_parameters": row[5] if len(row) > 5 else 0,
                "total_code_blocks": row[6] if len(row) > 6 else 0,
                "total_size_bytes": row[7] if len(row) > 7 else 0,
                "avg_function_complexity": row[8] if len(row) > 8 else 0
            }
        else:
            overview_data = {
                "total_files": 0,
                "total_functions": 0,
                "total_classes": 0,
                "total_symbols": 0,
                "total_assignments": 0,
                "total_parameters": 0,
                "total_code_blocks": 0,
                "total_size_bytes": 0,
                "avg_function_complexity": 0
            }

        return _success_response(overview_data)

    except Exception as e:
        logger.error(f"Codebase overview failed: {e}")
        return _error_response(e)


@mcp.tool()
async def analyze_code_structure(
    analysis_type: str,
    threshold: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run predefined analysis queries for code structure insights.

    Args:
        analysis_type: Type of analysis ('complexity', 'unused', 'parameters', 'nesting')
        threshold: Optional threshold values for analysis

    Returns:
        Analysis results with actionable insights
    """
    # Check initialization state first
    if not init_state.is_complete:
        return _initializing_response()

    if not analyzer:
        return _error_response(RuntimeError("CodeGraphAnalyzer not initialized"))

    try:
        analysis_methods = {
            "complexity": analyzer.find_complex_functions,
            "unused": analyzer.find_unused_functions,
            "parameters": analyzer.analyze_parameter_complexity,
            "nesting": analyzer.find_complex_code_blocks
        }

        if analysis_type not in analysis_methods:
            return _error_response(ValueError(f"Unknown analysis type: {analysis_type}. Available: {list(analysis_methods.keys())}"))

        method = analysis_methods[analysis_type]

        # Call method with or without threshold
        if threshold is not None and analysis_type in ["complexity", "parameters", "nesting"]:
            result = await asyncio.get_event_loop().run_in_executor(
                None, method, threshold
            )
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                None, method
            )

        # Convert result to usable format
        if result and hasattr(result, 'get_as_df'):
            df = result.get_as_df()
            analysis_data = {
                "analysis_type": analysis_type,
                "threshold": threshold,
                "results": df.to_dict('records') if not df.empty else [],
                "count": len(df),
                "timestamp": int(time.time())
            }
        else:
            analysis_data = {
                "analysis_type": analysis_type,
                "threshold": threshold,
                "results": [],
                "count": 0,
                "timestamp": int(time.time())
            }

        return _success_response(analysis_data)

    except Exception as e:
        logger.error(f"Code structure analysis failed: {e}")
        return _error_response(e)


# MCP Prompt Implementation

@mcp.prompt()
async def generate_kuzu_cypher(
    description: str,
    context: Optional[str] = None
) -> str:
    """
    Generate Cypher queries from natural language for graph-sitter code analysis.

    Args:
        description: Natural language description of desired query
        context: Additional context about the codebase

    Returns:
        Generated Cypher query with explanation
    """
    # Get schema context for better query generation
    if kuzu_sync:
        try:
            schema_result = await get_schema()
            schema_context = schema_result.get("data", {})
        except:
            schema_context = {}
    else:
        schema_context = {}

    # Template-based query generation with common patterns
    templates = {
        "find functions": """
-- Find all functions in the codebase
MATCH (f:Function)
RETURN f.name, f.file_path, f.complexity, f.start_line
ORDER BY f.complexity DESC
LIMIT 50;""",

        "list files": """
-- List all files with basic information
MATCH (file:File)
RETURN file.path, file.language, file.size
ORDER BY file.size DESC
LIMIT 20;""",

        "function calls": """
-- Find function call relationships
MATCH (caller:Function)-[:FUNCTION_CALLS]->(callee:Function)
RETURN caller.name as caller, callee.name as callee,
       caller.file_path as caller_file
ORDER BY caller.name
LIMIT 100;""",

        "complex functions": """
-- Find functions with high complexity
MATCH (f:Function)
WHERE f.complexity > 10
RETURN f.name, f.file_path, f.complexity, f.start_line
ORDER BY f.complexity DESC
LIMIT 20;""",

        "unused functions": """
-- Find potentially unused functions
MATCH (f:Function)
WHERE NOT exists {
    MATCH ()-[:FUNCTION_CALLS]->(f)
}
AND NOT f.name IN ['__init__', 'main', '__main__']
RETURN f.name, f.file_path, f.start_line
ORDER BY f.name;""",

        "file structure": """
-- Analyze file structure and function distribution
MATCH (file:File)-[:CONTAINS_FUNCTION]->(f:Function)
WITH file, count(f) as function_count
RETURN file.path, function_count, file.size
ORDER BY function_count DESC
LIMIT 30;""",

        "class methods": """
-- Find classes and their methods
MATCH (c:Class)-[:CLASS_METHOD]->(m:Function)
RETURN c.name as class_name, m.name as method_name,
       c.file_path, m.complexity
ORDER BY c.name, m.name;""",

        "symbols": """
-- Analyze symbol usage patterns
MATCH (s:Symbol)
RETURN s.kind, s.scope, count(s) as count
ORDER BY count DESC;""",

        "parameters": """
-- Find functions with many parameters
MATCH (f:Function)-[:HAS_PARAMETER]->(p:Parameter)
WITH f, count(p) as param_count
WHERE param_count > 5
RETURN f.name, f.file_path, param_count
ORDER BY param_count DESC;"""
    }

    # Simple keyword matching for template selection
    desc_lower = description.lower()

    for keyword, template in templates.items():
        if keyword in desc_lower:
            explanation = f"-- Generated from: {description}\n-- Pattern matched: {keyword}\n-- Context: {context or 'General codebase analysis'}\n"
            # TODO: Future enhancement - integrate with LLM API for sophisticated generation
            # Could use schema_context and context parameter to refine the query further
            return explanation + template

    # Default exploration query
    default_query = f"""-- Generated from: {description}
-- Context: {context or 'General exploration'}
-- Default exploration query - shows node type distribution
MATCH (n)
RETURN labels(n)[0] as node_type, count(n) as count
ORDER BY count DESC
LIMIT 10;"""

    return default_query


# MCP Resources Implementation

@mcp.resource("graph-sitter://codebase")
async def codebase_graph() -> str:
    """
    Current graph structure as JSON representation.

    Returns:
        JSON representation of the current codebase graph state
    """
    # Check initialization state first
    if not init_state.is_complete:
        return json.dumps(_initializing_response())

    if not kuzu_sync:
        return json.dumps(_error_response(RuntimeError("KuzuDB not initialized")))

    try:
        # Get basic graph structure statistics
        nodes_query = """
        MATCH (n)
        RETURN labels(n)[0] as type, count(n) as count
        ORDER BY count DESC
        """

        rels_query = """
        MATCH ()-[r]->()
        RETURN type(r) as relationship, count(r) as count
        ORDER BY count DESC
        """

        nodes_result = await asyncio.get_event_loop().run_in_executor(
            None, kuzu_sync.query, nodes_query
        )
        rels_result = await asyncio.get_event_loop().run_in_executor(
            None, kuzu_sync.query, rels_query
        )

        # Convert results to dictionaries
        nodes_data = nodes_result.get_as_df().to_dict('records') if nodes_result and hasattr(nodes_result, 'get_as_df') else []
        rels_data = rels_result.get_as_df().to_dict('records') if rels_result and hasattr(rels_result, 'get_as_df') else []

        graph_structure = {
            "nodes": nodes_data,
            "relationships": rels_data,
            "timestamp": int(time.time()),
            "description": "Current graph-sitter codebase structure in KuzuDB"
        }

        return json.dumps(_success_response(graph_structure), indent=2)

    except Exception as e:
        logger.error(f"Codebase resource failed: {e}")
        return json.dumps(_error_response(e), indent=2)


@mcp.resource("graph-sitter://sync-status")
async def sync_status() -> str:
    """
    Synchronization status, last update times, statistics.

    Returns:
        JSON representation of sync health and state monitoring
    """
    # Check initialization state first
    if not init_state.is_complete:
        return json.dumps(_initializing_response())

    if not kuzu_sync:
        return json.dumps(_error_response(RuntimeError("KuzuDB not initialized")))

    try:
        # Get database statistics
        stats = await asyncio.get_event_loop().run_in_executor(
            None, kuzu_sync.get_stats
        )

        sync_info = {
            "database_stats": stats,
            "sync_timestamp": int(time.time()),
            "status": "active" if kuzu_sync else "inactive",
            "codebase_initialized": codebase is not None,
            "analyzer_initialized": analyzer is not None,
            "database_path": str(kuzu_sync.db_path) if kuzu_sync else None
        }

        return json.dumps(_success_response(sync_info), indent=2)

    except Exception as e:
        logger.error(f"Sync status resource failed: {e}")
        return json.dumps(_error_response(e), indent=2)


async def initialize_server(
    project_path: Path,
    db_path: Optional[Path] = None,
    enable_monitoring: bool = True
) -> None:
    """
    Initialize the MCP server with KuzuDB and codebase.

    Args:
        project_path: Path to the codebase
        db_path: Optional path to KuzuDB database
        enable_monitoring: Whether to enable monitoring
    """
    global codebase, kuzu_sync, analyzer

    try:
        # Initialize codebase
        logger.info(f"Initializing codebase from {project_path}")
        codebase = Codebase(str(project_path))

        # Initialize KuzuDB sync
        db_path_str = str(db_path) if db_path else str(project_path / "code_graph.kuzu")
        kuzu_sync = KuzuSync(codebase, db_path_str)
        logger.info("KuzuSync initialized successfully")

        # Initialize analyzer
        if enable_monitoring:
            analyzer = CodeGraphAnalyzer(kuzu_sync)
            logger.info("CodeGraphAnalyzer initialized successfully")

    except Exception as e:
        logger.error(f"Server initialization failed: {e}")
        raise




def setup_logging(log_level: str) -> None:
    """Setup colorlog logging configuration."""
    log_colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        log_colors=log_colors
    ))

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        description="Graph-sitter KuzuDB MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --project-path /path/to/codebase
  %(prog)s --project-path . --db-path ./custom.kuzu --log-level DEBUG
        """
    )
    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path.cwd(),
        help="Path to the codebase (default: current directory)"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to KuzuDB database (default: project_path/code_graph.kuzu)"
    )
    parser.add_argument(
        "--enable-monitoring",
        action="store_true",
        default=True,
        help="Enable real-time monitoring (default: True)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Register cleanup handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup_server)
    logger.info("Registered cleanup handlers for graceful shutdown")

    # Validate project path
    if not args.project_path.exists():
        logger.error(f"Project path does not exist: {args.project_path}")
        sys.exit(1)

    # Start background initialization (non-blocking)
    logger.info("Starting background initialization...")
    start_background_initialization(
        str(args.project_path),
        str(args.db_path) if args.db_path else None,
        args.enable_monitoring
    )

    logger.info("MCP server starting on stdio transport (initialization running in background)...")
    # Run the MCP server - this will handle the async event loop internally
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()