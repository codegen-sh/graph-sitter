"""Real-time code monitoring with watchfiles integration."""

import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, Set, Optional, Callable, List

from watchfiles import awatch, Change
from graph_sitter.core.codebase import Codebase
from graph_sitter.shared.logging.get_logger import get_logger
from .sync import KuzuSync

logger = get_logger(__name__)


class CodeMonitor:
    """Real-time file monitoring and KuzuDB synchronization."""

    def __init__(
        self,
        codebase: Codebase,
        kuzu_sync: KuzuSync,
        watch_paths: Optional[List[str]] = None,
        debounce_delay: float = 0.5,
        ignore_patterns: Optional[Set[str]] = None
    ):
        self.codebase = codebase
        self.kuzu_sync = kuzu_sync
        self.watch_paths = watch_paths or [str(Path(codebase.root_path))]
        self.debounce_delay = debounce_delay
        self.ignore_patterns = ignore_patterns or {
            "*.pyc", "*.pyo", "__pycache__", ".git", ".kuzu",
            "node_modules", ".venv", "venv", "*.log"
        }

        self._running = False
        self._debounce_timers: Dict[str, threading.Timer] = {}
        self._lock = threading.RLock()
        self._update_callbacks: List[Callable[[str, str], None]] = []

    def add_update_callback(self, callback: Callable[[str, str], None]):
        """Add callback for file update events.

        Args:
            callback: Function that takes (file_path, change_type) as parameters
        """
        self._update_callbacks.append(callback)

    def _should_ignore(self, file_path: str) -> bool:
        """Check if file should be ignored based on patterns."""
        path = Path(file_path)

        # Check file extension and patterns
        for pattern in self.ignore_patterns:
            if pattern.startswith("*."):
                if path.suffix == pattern[1:]:
                    return True
            elif pattern in str(path):
                return True

        # Only watch Python and TypeScript files
        if path.suffix not in {'.py', '.ts', '.tsx', '.js', '.jsx'}:
            return True

        return False

    def _debounced_update(self, file_path: str, change_type: str):
        """Handle debounced file updates."""
        with self._lock:
            # Cancel existing timer for this file
            if file_path in self._debounce_timers:
                self._debounce_timers[file_path].cancel()

            # Create new timer
            timer = threading.Timer(
                self.debounce_delay,
                self._process_file_change,
                args=[file_path, change_type]
            )
            self._debounce_timers[file_path] = timer
            timer.start()

    def _process_file_change(self, file_path: str, change_type: str):
        """Process a file change after debounce delay."""
        try:
            with self._lock:
                # Remove from timers
                self._debounce_timers.pop(file_path, None)

            logger.debug(f"Processing {change_type} for {file_path}")

            if change_type in ["added", "modified"]:
                # Refresh codebase for this file
                self.codebase.refresh()

                # Sync to KuzuDB
                self.kuzu_sync.sync_file(file_path)

            elif change_type == "deleted":
                # Remove from KuzuDB
                self.kuzu_sync._clear_file_data(file_path)

            # Trigger callbacks
            for callback in self._update_callbacks:
                try:
                    callback(file_path, change_type)
                except Exception as e:
                    logger.error(f"Update callback failed: {e}")

            logger.debug(f"Completed processing {change_type} for {file_path}")

        except Exception as e:
            logger.error(f"Failed to process file change {file_path}: {e}")

    async def _watch_files(self):
        """Async file watching loop."""
        logger.info(f"Starting file monitoring for paths: {self.watch_paths}")

        try:
            async for changes in awatch(*self.watch_paths, recursive=True):
                if not self._running:
                    break

                for change, file_path in changes:
                    file_path_str = str(file_path)

                    # Check if we should ignore this file
                    if self._should_ignore(file_path_str):
                        continue

                    # Map change type
                    change_type = {
                        Change.added: "added",
                        Change.modified: "modified",
                        Change.deleted: "deleted"
                    }.get(change, "unknown")

                    if change_type != "unknown":
                        logger.debug(f"File {change_type}: {file_path_str}")
                        self._debounced_update(file_path_str, change_type)

        except Exception as e:
            logger.error(f"File watching error: {e}")
            raise

    def start_monitoring(self):
        """Start real-time file monitoring."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._running = True
        logger.info("Starting code monitor")

        # Run the async watch loop in a thread
        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._watch_files())
            finally:
                loop.close()

        self._watch_thread = threading.Thread(target=run_async_loop, daemon=True)
        self._watch_thread.start()

        return self._watch_thread

    def stop_monitoring(self):
        """Stop file monitoring."""
        if not self._running:
            return

        logger.info("Stopping code monitor")
        self._running = False

        # Cancel all pending timers
        with self._lock:
            for timer in self._debounce_timers.values():
                timer.cancel()
            self._debounce_timers.clear()

        # Wait for thread to finish
        if hasattr(self, '_watch_thread') and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5.0)

    def __enter__(self):
        """Context manager entry."""
        self.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()


class CodeGraphAnalyzer:
    """Analyze code patterns using KuzuDB queries."""

    def __init__(self, kuzu_sync: KuzuSync):
        self.kuzu_sync = kuzu_sync

    def find_complex_functions(self, threshold: int = 10):
        """Find functions with high complexity."""
        query = """
        MATCH (f:Function)
        WHERE f.complexity > $threshold
        RETURN f.name, f.file_path, f.complexity, f.start_line
        ORDER BY f.complexity DESC
        """
        return self.kuzu_sync.query(query, {"threshold": threshold})

    def find_large_classes(self, threshold: int = 20):
        """Find classes with many methods."""
        query = """
        MATCH (c:Class)
        WHERE c.methods_count > $threshold
        RETURN c.name, c.file_path, c.methods_count, c.start_line
        ORDER BY c.methods_count DESC
        """
        return self.kuzu_sync.query(query, {"threshold": threshold})

    def find_unused_functions(self):
        """Find functions that are never called."""
        query = """
        MATCH (f:Function)
        WHERE NOT exists {
            MATCH ()-[:FUNCTION_CALLS]->(f)
        }
        AND NOT f.name IN ['__init__', 'main', '__main__']
        RETURN f.name, f.file_path, f.start_line
        ORDER BY f.name
        """
        return self.kuzu_sync.query(query)

    def find_function_call_chains(self, max_depth: int = 5):
        """Find function call chains."""
        query = f"""
        MATCH path = (start:Function)-[:FUNCTION_CALLS*1..{max_depth}]->(end:Function)
        WHERE start <> end
        RETURN
            start.name as start_function,
            end.name as end_function,
            length(path) as chain_length,
            [node in nodes(path) | node.name] as call_chain
        ORDER BY chain_length DESC
        LIMIT 20
        """
        return self.kuzu_sync.query(query)

    def find_import_dependencies(self, module_name: str):
        """Find all files that import a specific module."""
        query = """
        MATCH (file:File)-[:CONTAINS_IMPORT]->(imp:Import)
        WHERE imp.module_name CONTAINS $module
        RETURN file.path, imp.module_name, imp.imported_name, imp.alias
        ORDER BY file.path
        """
        return self.kuzu_sync.query(query, {"module": module_name})

    def get_file_metrics(self, file_path: str):
        """Get detailed metrics for a specific file."""
        query = """
        MATCH (file:File {path: $path})
        OPTIONAL MATCH (file)-[:CONTAINS_FUNCTION]->(func:Function)
        OPTIONAL MATCH (file)-[:CONTAINS_CLASS]->(cls:Class)
        OPTIONAL MATCH (file)-[:CONTAINS_IMPORT]->(imp:Import)
        RETURN
            file.path as file_path,
            file.size as file_size,
            file.language as language,
            count(DISTINCT func) as function_count,
            count(DISTINCT cls) as class_count,
            count(DISTINCT imp) as import_count,
            avg(func.complexity) as avg_complexity
        """
        return self.kuzu_sync.query(query, {"path": file_path})

    def get_codebase_overview(self):
        """Get overall codebase metrics."""
        query = """
        MATCH (file:File)
        OPTIONAL MATCH (file)-[:CONTAINS_FUNCTION]->(func:Function)
        OPTIONAL MATCH (file)-[:CONTAINS_CLASS]->(cls:Class)
        RETURN
            count(DISTINCT file) as total_files,
            count(DISTINCT func) as total_functions,
            count(DISTINCT cls) as total_classes,
            sum(file.size) as total_size,
            avg(func.complexity) as avg_function_complexity
        """
        return self.kuzu_sync.query(query)