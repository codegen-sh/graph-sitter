# Project 03: KuzuDB MCP Server Implementation

## Project Overview

Create a lean and efficient MCP (Model Context Protocol) server that exposes the existing graph-sitter KuzuDB integration capabilities through a standardized interface. This server will replicate the functionality of the reference `kuzu-mcp-server` implementation while leveraging the advanced graph-sitter codebase analysis capabilities built in Projects 01 and 02.

## Background Context

**Prerequisites**:
- Project 01: Basic KuzuDB integration with graph-sitter ✅ COMPLETED
- Project 02: Extended mapping with Symbol, Assignment, Interface, TypeAlias, Parameter, CodeBlock ✅ COMPLETED

**Integration Point**: The KuzuDB graph database now contains complete code structure mapping synchronized with graph-sitter's in-memory representation, enabling advanced code analysis queries.

## Technical Specification

### Core Requirements

**File Location**: `./src/graph_sitter/extensions/kuzu_map/kuzu_map_mcp.py`

**Dependencies**:
- FastMCP framework for MCP server implementation
- Existing KuzuSync functionality from graph-sitter extensions
- colorlog for structured logging
- Standard asyncio for async operations

### MCP Server Interface

#### Tools to Implement

1. **query**
   - **Purpose**: Execute Cypher queries on the graph-sitter synchronized KuzuDB
   - **Args**:
     - `cypher_query: str` - The Cypher query to execute
     - `parameters: Optional[Dict[str, Any]]` - Query parameters
   - **Returns**: Query results as structured data (rows, columns, metadata)

2. **get_schema**
   - **Purpose**: Retrieve complete database schema including graph-sitter specific tables
   - **Args**: None
   - **Returns**: Schema information (node tables, relationship tables, properties)

3. **get_codebase_overview**
   - **Purpose**: Get high-level statistics about the synchronized codebase
   - **Args**: None
   - **Returns**: Entity counts, file statistics, complexity metrics

4. **analyze_code_structure**
   - **Purpose**: Run predefined analysis queries (complex functions, unused symbols, etc.)
   - **Args**:
     - `analysis_type: str` - Type of analysis ('complexity', 'unused', 'parameters', etc.)
     - `threshold: Optional[int]` - Threshold values for analysis
   - **Returns**: Analysis results with actionable insights

#### Prompts to Implement

1. **generate_kuzu_cypher**
   - **Purpose**: Generate Cypher queries from natural language for graph-sitter code analysis
   - **Args**:
     - `description: str` - Natural language description of desired query
     - `context: Optional[str]` - Additional context about the codebase
   - **Returns**: Generated Cypher query with explanation

#### Resources to Expose

1. **codebase_graph**
   - **URI**: `graph-sitter://codebase`
   - **Content**: Current graph structure as JSON representation
   - **Purpose**: Allow MCP clients to inspect the current graph state

2. **sync_status**
   - **URI**: `graph-sitter://sync-status`
   - **Content**: Synchronization status, last update times, statistics
   - **Purpose**: Monitor health and state of graph-sitter ↔ KuzuDB sync

### Implementation Architecture

#### Core Components

**Server Initialization**:
```python
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP
import logging
import colorlog
import asyncio
import time
from pathlib import Path

# Import existing graph-sitter extensions
from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.kuzu_map import KuzuSync, CodeGraphAnalyzer

mcp = FastMCP("graph-sitter-kuzu")

# Global state management
codebase: Optional[Codebase] = None
kuzu_sync: Optional[KuzuSync] = None
analyzer: Optional[CodeGraphAnalyzer] = None
```

**Data Integration Strategy**:
- **No Adaptation Layer**: Direct use of existing KuzuSync and CodeGraphAnalyzer
- **Graph-sitter Native**: Leverage in-memory graph synchronization
- **Real-time Capable**: Support for live updates if monitoring is active
- **Transaction Integrity**: All operations respect KuzuDB transaction boundaries

#### Key Implementation Methods

**Query Execution**:
```python
@mcp.tool()
async def query(cypher_query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute Cypher query on graph-sitter synchronized KuzuDB"""
    try:
        result = kuzu_sync.query(cypher_query, parameters or {})
        return {
            "success": True,
            "rows": result.get_as_df().to_dict('records') if result else [],
            "row_count": len(result.get_as_df()) if result else 0,
            "execution_time_ms": # measure execution time
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
```

**Schema Extraction**:
```python
@mcp.tool()
async def get_schema() -> Dict[str, Any]:
    """Get complete database schema including graph-sitter tables"""
    schema_info = kuzu_sync.get_schema()

    return {
        "node_tables": schema_info["nodes"],
        "relationship_tables": schema_info["relationships"],
        "graph_sitter_specific": {
            "entities": ["File", "Function", "Class", "Symbol", "Assignment", "Parameter", "CodeBlock"],
            "analysis_capabilities": ["complexity", "unused_detection", "parameter_analysis"]
        }
    }
```

**Analysis Integration**:
```python
@mcp.tool()
async def analyze_code_structure(analysis_type: str, threshold: Optional[int] = None) -> Dict[str, Any]:
    """Run predefined code structure analysis"""
    analysis_methods = {
        "complexity": analyzer.find_complex_functions,
        "unused": analyzer.find_unused_symbols,
        "parameters": analyzer.analyze_parameter_complexity,
        "nesting": analyzer.find_complex_code_blocks
    }

    if analysis_type not in analysis_methods:
        return {"error": f"Unknown analysis type: {analysis_type}"}

    method = analysis_methods[analysis_type]
    kwargs = {"threshold": threshold} if threshold else {}

    results = method(**kwargs)
    return {
        "analysis_type": analysis_type,
        "results": results.to_dict('records') if hasattr(results, 'to_dict') else results,
        "timestamp": int(time.time())
    }
```

### Integration with Existing Infrastructure

#### Leverage Project 01 & 02 Capabilities

**Direct Integration Points**:
- `KuzuSync`: Database synchronization and querying
- `CodeGraphAnalyzer`: Advanced analysis capabilities
- `CodeMonitor`: Real-time update capabilities (optional)

**No Bridge Layer**: Following coding guidelines, directly use existing functionality without adaptation layers or backwards compatibility concerns.

#### Memory Persistence Strategy

**Graph-sitter Synchronization**:
- MCP server initializes with existing codebase
- KuzuDB contains current synchronized state
- Optional: Real-time updates if monitoring is active
- Graceful handling of sync status in responses

#### Configuration Management

**Server Parameters**:
- `--project-path`: Path to codebase (default: current directory)
- `--db-path`: KuzuDB database path (default: `./code_graph.kuzu`)
- `--enable-monitoring`: Enable real-time file monitoring (default: false)
- `--log-level`: Logging verbosity (default: INFO)

### Cypher Query Generation

#### Natural Language Processing

**Prompt Implementation**:
```python
@mcp.prompt()
async def generate_kuzu_cypher(description: str, context: Optional[str] = None) -> str:
    """Generate Cypher queries for graph-sitter code analysis"""

    schema_context = await get_schema()

    system_prompt = f"""
    Generate a Cypher query for graph-sitter code analysis based on: {description}

    Available Schema:
    {schema_context}

    Graph-sitter Specific Rules:
    - File nodes contain: path, language, loc, hash, last_analyzed
    - Function nodes contain: name, complexity, params_count, start_line
    - Symbol nodes contain: name, kind, scope, type_annotation
    - Use relationship traversals for code flow analysis
    - Consider complexity metrics for quality analysis
    - Leverage scope information for precise filtering

    Context: {context or "General codebase analysis"}

    Return only the Cypher query, properly formatted.
    """

    # Implementation would use appropriate LLM API or local model
    # For now, return template-based generation
    return _generate_template_query(description, schema_context)
```

### Error Handling and Resilience

#### Robust Error Management

**Transaction Safety**:
- All KuzuDB operations wrapped in try-catch
- Automatic transaction rollback on failures
- Graceful degradation for partial failures
- Detailed error reporting with context

**State Validation**:
- Verify codebase and database initialization
- Check sync status before operations
- Handle missing or corrupted data gracefully
- Provide meaningful error messages

### Testing Strategy

#### Verification Approach

**Unit Testing**:
- Test each MCP tool independently
- Validate query generation and execution
- Test error handling scenarios
- Verify schema extraction accuracy

**Integration Testing**:
- Test with real graph-sitter codebase
- Validate sync state consistency
- Test complex analysis queries
- Performance testing with large codebases

#### Success Criteria

**Functional Requirements**:
- [ ] All MCP tools respond correctly
- [ ] Query results match direct KuzuSync calls
- [ ] Schema information is complete and accurate
- [ ] Analysis tools provide actionable insights
- [ ] Error handling is robust and informative

**Performance Requirements**:
- Query response time < 1 second for standard queries
- Schema retrieval < 100ms
- Analysis operations scale with codebase size
- Memory usage remains stable during operation

## Implementation Plan

### Phase 1: Core Server Setup
1. **MCP Server Scaffold**: Basic FastMCP server with logging
2. **Integration Layer**: Connect to existing KuzuSync and analyzer
3. **Basic Tools**: Implement `query` and `get_schema` tools
4. **Testing**: Verify basic functionality with test queries

### Phase 2: Advanced Features
1. **Analysis Tools**: Implement `get_codebase_overview` and `analyze_code_structure`
2. **Resource Exposure**: Implement graph and sync status resources
3. **Query Generation**: Implement Cypher generation prompt
4. **Configuration**: Add command-line configuration support

### Phase 3: Production Readiness
1. **Error Handling**: Comprehensive error management
2. **Performance**: Optimize query execution and response formatting
3. **Documentation**: Usage examples and API documentation
4. **Testing**: Full integration test suite

## Agent Execution Strategy

### Recommended Implementation Approach

**Primary Agent**: `python-implementation`
- **Task Scope**: Complete MCP server implementation in single focused session
- **Key Responsibilities**:
  - FastMCP server setup with all tools and prompts
  - Integration with existing KuzuSync functionality
  - Error handling and logging implementation
  - Basic testing and validation

**Handoff Specifications**:
```
Context: MCP server for graph-sitter KuzuDB integration
Input: This specification document + existing Projects 01/02 codebase
Output: Working MCP server at ./src/graph_sitter/extensions/kuzu_map/kuzu_map_mcp.py
Success Criteria: Server starts, responds to MCP protocol, executes queries
```

**Coordination Protocol**:
- Single-agent implementation given clear specification
- Self-contained task with existing infrastructure dependencies
- Validation through direct server testing
- No peer agent dependencies required

### Alternative Multi-Agent Approach

If complexity exceeds single-agent capacity:

**Agent 1 - architect-coordinator**: Design validation and coordination
**Agent 2 - python-implementation**: Core server implementation
**Agent 3 - python-implementation**: Testing and validation

**Handoff Sequence**:
1. Coordinator validates specification against existing codebase
2. Implementer creates core server functionality
3. Validator creates test suite and verifies operation

## Success Metrics

### Technical Validation
- [ ] MCP server starts without errors
- [ ] All 4 tools respond correctly to valid inputs
- [ ] Query tool executes Cypher on KuzuDB successfully
- [ ] Schema tool returns complete graph-sitter schema
- [ ] Analysis tools leverage existing CodeGraphAnalyzer
- [ ] Error handling provides meaningful feedback

### Integration Validation
- [ ] Server integrates cleanly with existing extensions
- [ ] No disruption to existing KuzuSync functionality
- [ ] Follows graph-sitter coding guidelines (no bridges/adapters)
- [ ] Memory usage remains efficient
- [ ] Performance meets specification requirements

### Operational Validation
- [ ] Server can be started via command line
- [ ] Configuration options work as specified
- [ ] Logging provides appropriate debugging information
- [ ] Graceful shutdown on interrupt signals
- [ ] Compatible with MCP client tools

---

**Project Status**: 📋 SPECIFICATION COMPLETE
**Ready for Implementation**: ✅ YES
**Dependencies Satisfied**: ✅ Projects 01 & 02 completed
**Implementation Approach**: Single python-implementation agent deployment