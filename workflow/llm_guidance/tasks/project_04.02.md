# Project 04.02: Analyzer Dependency Resolution

## Sub-Task Overview

**Parent Project**: Project 04 - MCP Self-Inspection Implementation Fixes
**Priority**: 🔥 HIGH PRIORITY - Core functionality broken
**Complexity**: 🟢 LOW-MEDIUM - Clear fix with straightforward implementation

## Problem Definition

### Current Issue
```python
# Line 334 in kuzu_map_mcp.py - Logic Flaw Detected
if not analyzer:
    return _error_response(RuntimeError("CodeGraphAnalyzer not initialized"))
```

**Root Cause**: The analyzer is only created when `enable_monitoring=True`, but `get_codebase_overview` always requires it.

**Impact**:
- `get_codebase_overview` fails when monitoring is disabled
- Core MCP functionality broken for common use case
- Inconsistent API behavior based on configuration

### Current Problematic Code Pattern
```python
# In initialize() function
if enable_monitoring:
    analyzer = CodeGraphAnalyzer(kuzu_sync)  # Only created if monitoring enabled
else:
    analyzer = None  # Always None when monitoring disabled

# Later in get_codebase_overview
@mcp.tool()
async def get_codebase_overview() -> Dict[str, Any]:
    if not analyzer:  # This always fails when monitoring=False
        return _error_response(RuntimeError("CodeGraphAnalyzer not initialized"))
```

## Technical Solution

### Analyzer Management Strategy

**1. Separate Analyzer Creation from Monitoring**
The analyzer provides analysis capabilities that are valuable regardless of file monitoring status. Monitoring only affects real-time updates, not the ability to analyze existing data.

**2. Lazy Initialization Pattern**
Create analyzer when first needed, not tied to monitoring configuration.

### Implementation Details

**1. Analyzer Availability Function**
```python
def ensure_analyzer_available() -> CodeGraphAnalyzer:
    """Ensure analyzer is available, creating if necessary"""
    global analyzer, kuzu_sync

    if analyzer is None:
        if kuzu_sync is None:
            raise RuntimeError("KuzuSync must be initialized before analyzer")

        logger.info("Creating CodeGraphAnalyzer (independent of monitoring state)")
        analyzer = CodeGraphAnalyzer(kuzu_sync)
        logger.info("CodeGraphAnalyzer created successfully")

    return analyzer

def is_analyzer_available() -> bool:
    """Check if analyzer is available or can be created"""
    return kuzu_sync is not None
```

**2. Enhanced Tool Implementation**
```python
@mcp.tool()
@requires_initialization  # From 04.01
async def get_codebase_overview() -> Dict[str, Any]:
    """Get high-level statistics about the synchronized codebase"""
    try:
        # Ensure analyzer is available
        if not is_analyzer_available():
            return _error_response(RuntimeError("Database not initialized"))

        current_analyzer = ensure_analyzer_available()

        # Basic statistics
        overview = {
            "database_stats": _get_database_statistics(),
            "file_stats": _get_file_statistics(current_analyzer),
            "code_stats": _get_code_statistics(current_analyzer),
            "complexity_stats": _get_complexity_statistics(current_analyzer),
            "monitoring_status": {
                "enabled": enable_monitoring,
                "active": monitor is not None and monitor.is_monitoring
            }
        }

        return {
            "status": "success",
            "overview": overview,
            "generated_at": time.time()
        }

    except Exception as e:
        logger.error(f"Error getting codebase overview: {e}")
        return _error_response(e)

def _get_database_statistics() -> Dict[str, Any]:
    """Get basic database statistics"""
    stats = {}

    try:
        # Count entities in database
        for entity_type in ["File", "Function", "Class", "Import"]:
            try:
                result = kuzu_sync.query(f"MATCH (n:{entity_type}) RETURN count(n) as count")
                count = result.get_next()[0] if result.has_next() else 0
                stats[f"{entity_type.lower()}_count"] = count
            except Exception as e:
                logger.warning(f"Could not count {entity_type}: {e}")
                stats[f"{entity_type.lower()}_count"] = 0

        # Get database size info
        stats["database_path"] = str(db_path)
        stats["database_exists"] = db_path.exists()

    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        stats["error"] = str(e)

    return stats

def _get_file_statistics(analyzer: CodeGraphAnalyzer) -> Dict[str, Any]:
    """Get file-level statistics"""
    try:
        # Use analyzer to get file stats
        file_stats = analyzer.get_file_statistics()
        return file_stats
    except Exception as e:
        logger.error(f"Error getting file stats: {e}")
        # Fallback to basic database query
        return _get_basic_file_stats()

def _get_basic_file_stats() -> Dict[str, Any]:
    """Fallback file statistics from database only"""
    try:
        result = kuzu_sync.query("""
            MATCH (f:File)
            RETURN
                count(f) as total_files,
                sum(f.loc) as total_loc,
                avg(f.loc) as avg_loc_per_file
        """)

        if result.has_next():
            row = result.get_next()
            return {
                "total_files": row[0],
                "total_lines_of_code": row[1] or 0,
                "average_loc_per_file": round(row[2] or 0, 1)
            }
        else:
            return {"total_files": 0, "total_lines_of_code": 0}

    except Exception as e:
        logger.error(f"Error getting basic file stats: {e}")
        return {"error": str(e)}
```

**3. Modified Initialization Process**
```python
async def initialize():
    """Initialize server components with proper analyzer handling"""
    try:
        global codebase, kuzu_sync, analyzer, monitor, init_state

        logger.info("Starting MCP server initialization...")

        # Phase 1: Load codebase and initialize database
        _initialize_codebase_with_progress()  # From 04.01

        # Phase 2: Setup monitoring (if enabled)
        if enable_monitoring:
            logger.info("Setting up file monitoring...")
            monitor = CodeMonitor(codebase, kuzu_sync)
            monitor.start_monitoring()
            logger.info("File monitoring active")
        else:
            logger.info("File monitoring disabled")
            monitor = None

        # NOTE: Analyzer is created lazily when first needed
        # This decouples analyzer availability from monitoring configuration

        logger.info("MCP server initialization completed")

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        init_state.mark_failed(e)
        raise
```

### Fallback Functionality

**4. Graceful Degradation**
When analyzer operations fail, provide basic functionality using direct database queries:

```python
def _safe_analyzer_operation(operation_name: str, analyzer_method: Callable, fallback_method: Callable) -> Any:
    """Safely execute analyzer operation with fallback"""
    try:
        current_analyzer = ensure_analyzer_available()
        return analyzer_method(current_analyzer)
    except Exception as e:
        logger.warning(f"Analyzer operation {operation_name} failed, using fallback: {e}")
        return fallback_method()

# Usage example
@mcp.tool()
@requires_initialization
async def analyze_code_structure(analysis_type: str, threshold: Optional[int] = None) -> Dict[str, Any]:
    """Run code structure analysis with fallback support"""

    def get_complexity_analysis(analyzer):
        return analyzer.find_complex_functions(threshold or 10)

    def fallback_complexity_analysis():
        # Direct database query fallback
        query = """
            MATCH (f:Function)
            WHERE f.complexity > $threshold
            RETURN f.name, f.file_path, f.complexity
            ORDER BY f.complexity DESC
            LIMIT 50
        """
        result = kuzu_sync.query(query, {"threshold": threshold or 10})
        return result.get_as_df() if result else pd.DataFrame()

    if analysis_type == "complexity":
        results = _safe_analyzer_operation(
            "complexity_analysis",
            get_complexity_analysis,
            fallback_complexity_analysis
        )
        return {
            "analysis_type": analysis_type,
            "results": results.to_dict('records') if hasattr(results, 'to_dict') else [],
            "threshold": threshold,
            "fallback_used": analyzer is None
        }
    else:
        return _error_response(ValueError(f"Unknown analysis type: {analysis_type}"))
```

## Implementation Steps

### Step 1: Add Analyzer Management Functions
**Location**: `src/graph_sitter/extensions/kuzu_map/kuzu_map_mcp.py`
**Add**: `ensure_analyzer_available()` and `is_analyzer_available()` functions

### Step 2: Fix get_codebase_overview
**Action**: Replace analyzer dependency check with proper initialization
**Add**: Database statistics and fallback functionality

### Step 3: Update Initialization Process
**Action**: Remove analyzer creation from monitoring conditional
**Add**: Lazy analyzer initialization documentation

### Step 4: Add Fallback Methods
**Action**: Implement direct database query fallbacks for core statistics
**Add**: Safe operation wrapper for graceful degradation

### Step 5: Update analyze_code_structure
**Action**: Add fallback support for when analyzer is unavailable
**Add**: Clear indication when fallback functionality is used

## Configuration Clarity

### Updated Server Behavior
```python
# Configuration scenarios:
# 1. enable_monitoring=True:  Live file updates + analyzer
# 2. enable_monitoring=False: Static analysis + analyzer (no live updates)

# Both scenarios provide:
# - get_codebase_overview (works)
# - analyze_code_structure (works)
# - query (works)
# - get_schema (works)

# Only scenario 1 provides:
# - Real-time file change updates
# - Live monitoring statistics
```

## Success Criteria

### Functional Requirements
- [ ] `get_codebase_overview` works regardless of monitoring setting
- [ ] `analyze_code_structure` provides basic functionality always
- [ ] Clear distinction between monitoring and analysis capabilities
- [ ] Graceful fallback when analyzer operations fail
- [ ] Consistent API behavior across configurations

### User Experience Requirements
- [ ] No "analyzer not initialized" errors for basic operations
- [ ] Clear indication when fallback functionality is used
- [ ] Consistent response formats regardless of configuration
- [ ] Helpful error messages when operations genuinely fail

### Technical Requirements
- [ ] Lazy analyzer initialization
- [ ] Thread-safe analyzer creation
- [ ] Minimal performance impact from changes
- [ ] Proper error handling and logging
- [ ] Clean separation of concerns

## Validation Plan

### Test Scenarios
1. **Monitoring Disabled**: Start server with `enable_monitoring=False`
2. **Monitoring Enabled**: Start server with `enable_monitoring=True`
3. **Analyzer Failure**: Simulate analyzer initialization failure
4. **Database Only**: Test fallback functionality with direct queries
5. **Lazy Initialization**: Verify analyzer created only when needed

### Testing Commands
```bash
# Test with monitoring disabled
python -m graph_sitter.extensions.kuzu_map.kuzu_map_mcp --enable-monitoring=false

# Test codebase overview in both modes
mcp-client get_codebase_overview

# Test analysis functionality
mcp-client analyze_code_structure --analysis-type complexity --threshold 5

# Verify analyzer status
mcp-client get_server_status
```

---

**Sub-Task Status**: 📋 SPECIFICATION COMPLETE
**Implementation Priority**: 🔥 HIGH - Fixes broken core functionality
**Estimated Complexity**: 🟢 LOW-MEDIUM - Straightforward logic fix
**Dependencies**: Can be implemented alongside 04.01 (initialization fixes)