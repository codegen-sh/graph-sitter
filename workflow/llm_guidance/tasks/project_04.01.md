# Project 04.01: Initialization Race Condition Fix

## Sub-Task Overview

**Parent Project**: Project 04 - MCP Self-Inspection Implementation Fixes
**Priority**: 🔥 HIGH PRIORITY - Critical system reliability issue
**Complexity**: 🟡 MEDIUM - Requires careful state management implementation

## Problem Definition

### Current Issue
The MCP server initialization runs in a background thread taking 300+ seconds to process 1136+ files. During this period:
- Server reports as "ready" to MCP clients
- Tool calls fail with "CodeGraphAnalyzer not initialized" errors
- Users receive confusing error messages instead of progress updates
- No indication of initialization progress or estimated completion time

### Root Cause Analysis
```python
# Current problematic pattern in kuzu_map_mcp.py
def initialize():
    # Background thread starts immediately
    init_thread = threading.Thread(target=_initialize_codebase, daemon=True)
    init_thread.start()
    # Server immediately reports ready - PROBLEM!

@mcp.tool()
def get_codebase_overview():
    # This can be called before initialization completes
    if not analyzer:  # analyzer is None during initialization
        return _error_response(RuntimeError("CodeGraphAnalyzer not initialized"))
```

## Technical Solution

### State Management Implementation

**1. Initialization State Class**
```python
import time
import threading
from enum import Enum
from typing import Optional

class InitStatus(Enum):
    NOT_STARTED = "not_started"
    INITIALIZING = "initializing"
    COMPLETED = "completed"
    FAILED = "failed"

class InitializationState:
    def __init__(self):
        self.status = InitStatus.NOT_STARTED
        self.error: Optional[Exception] = None
        self.start_time: Optional[float] = None
        self.completion_time: Optional[float] = None
        self.files_processed: int = 0
        self.total_files: int = 0
        self.current_operation: str = ""
        self._lock = threading.RLock()

    def mark_started(self, total_files: int):
        with self._lock:
            self.status = InitStatus.INITIALIZING
            self.start_time = time.time()
            self.total_files = total_files
            self.files_processed = 0

    def update_progress(self, files_processed: int, operation: str = ""):
        with self._lock:
            self.files_processed = files_processed
            self.current_operation = operation

    def mark_completed(self):
        with self._lock:
            self.status = InitStatus.COMPLETED
            self.completion_time = time.time()

    def mark_failed(self, error: Exception):
        with self._lock:
            self.status = InitStatus.FAILED
            self.error = error

    @property
    def is_complete(self) -> bool:
        with self._lock:
            return self.status == InitStatus.COMPLETED

    @property
    def elapsed_time(self) -> Optional[float]:
        with self._lock:
            if self.start_time is None:
                return None
            end_time = self.completion_time or time.time()
            return end_time - self.start_time

    @property
    def progress_percentage(self) -> float:
        with self._lock:
            if self.total_files == 0:
                return 0.0
            return (self.files_processed / self.total_files) * 100

    def get_status_dict(self) -> dict:
        with self._lock:
            return {
                "status": self.status.value,
                "is_complete": self.is_complete,
                "error": str(self.error) if self.error else None,
                "progress": {
                    "files_processed": self.files_processed,
                    "total_files": self.total_files,
                    "percentage": round(self.progress_percentage, 1),
                    "current_operation": self.current_operation
                },
                "timing": {
                    "elapsed_seconds": round(self.elapsed_time or 0, 1),
                    "estimated_remaining": self._estimate_remaining_time()
                }
            }

    def _estimate_remaining_time(self) -> Optional[float]:
        with self._lock:
            if (self.elapsed_time is None or
                self.files_processed == 0 or
                self.status != InitStatus.INITIALIZING):
                return None

            rate = self.files_processed / self.elapsed_time
            remaining_files = self.total_files - self.files_processed
            return remaining_files / rate if rate > 0 else None
```

### Tool Decoration System

**2. Initialization Guard Decorator**
```python
from functools import wraps
from typing import Callable, Any, Dict

def requires_initialization(func: Callable) -> Callable:
    """Decorator that ensures tools handle initialization state properly"""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Dict[str, Any]:
        global init_state

        if init_state.status == InitStatus.NOT_STARTED:
            return _not_started_response()
        elif init_state.status == InitStatus.INITIALIZING:
            return _initializing_response(init_state)
        elif init_state.status == InitStatus.FAILED:
            return _initialization_failed_response(init_state)
        elif init_state.status == InitStatus.COMPLETED:
            return await func(*args, **kwargs)
        else:
            return _error_response(RuntimeError(f"Unknown initialization status: {init_state.status}"))

    return wrapper

def _not_started_response() -> Dict[str, Any]:
    return {
        "status": "not_ready",
        "message": "Server has not started initialization yet",
        "action_required": "Please wait for server startup to begin"
    }

def _initializing_response(state: InitializationState) -> Dict[str, Any]:
    status_dict = state.get_status_dict()

    return {
        "status": "initializing",
        "message": f"Server is initializing codebase analysis ({status_dict['progress']['percentage']}% complete)",
        "progress": status_dict['progress'],
        "timing": status_dict['timing'],
        "recommendation": "Please wait for initialization to complete before retrying"
    }

def _initialization_failed_response(state: InitializationState) -> Dict[str, Any]:
    return {
        "status": "initialization_failed",
        "message": "Server initialization failed",
        "error": str(state.error) if state.error else "Unknown initialization error",
        "elapsed_time": state.elapsed_time,
        "recommendation": "Check server logs and restart server"
    }

def _error_response(error: Exception) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": str(error),
        "error_type": type(error).__name__,
        "timestamp": time.time()
    }
```

### Progressive Initialization Implementation

**3. Enhanced Initialization Process**
```python
# Global state instance
init_state = InitializationState()

def _initialize_codebase_with_progress():
    """Enhanced initialization with progress tracking"""
    try:
        global codebase, kuzu_sync, analyzer, init_state

        logger.info("Starting codebase initialization...")

        # Phase 1: Load codebase
        init_state.update_progress(0, "Loading codebase structure...")
        codebase = Codebase(project_path)

        total_files = len(codebase.files)
        init_state.mark_started(total_files)
        logger.info(f"Found {total_files} files to process")

        # Phase 2: Initialize KuzuDB
        init_state.update_progress(0, "Initializing KuzuDB...")
        kuzu_sync = KuzuSync(
            codebase=codebase,
            db_path=db_path,
            enable_monitoring=enable_monitoring
        )

        # Phase 3: Synchronize with progress updates
        init_state.update_progress(0, "Synchronizing codebase to database...")

        # Hook into KuzuSync to get progress updates
        original_sync_file = kuzu_sync._sync_file
        def sync_file_with_progress(file_obj, *args, **kwargs):
            result = original_sync_file(file_obj, *args, **kwargs)
            init_state.update_progress(
                init_state.files_processed + 1,
                f"Processed {file_obj.filepath.name}"
            )
            return result

        kuzu_sync._sync_file = sync_file_with_progress
        kuzu_sync.sync()

        # Phase 4: Initialize analyzer
        init_state.update_progress(total_files, "Initializing analyzer...")
        analyzer = CodeGraphAnalyzer(kuzu_sync) if enable_monitoring else None

        # Mark completion
        init_state.mark_completed()
        logger.info(f"Initialization completed in {init_state.elapsed_time:.1f} seconds")

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        init_state.mark_failed(e)
        raise

async def initialize():
    """Start background initialization with proper state management"""
    logger.info("Starting MCP server initialization...")

    init_thread = threading.Thread(
        target=_initialize_codebase_with_progress,
        name="CodebaseInit",
        daemon=False  # Don't make it daemon so we can track completion
    )
    init_thread.start()

    logger.info("Background initialization started")
```

## Implementation Steps

### Step 1: Add State Management
**Location**: `src/graph_sitter/extensions/kuzu_map/kuzu_map_mcp.py`
**Action**: Add `InitializationState` class and global `init_state` variable

### Step 2: Implement Decorator
**Location**: Same file, after state management
**Action**: Add `requires_initialization` decorator and response helpers

### Step 3: Apply Decorators to Tools
**Target Tools**:
- `@mcp.tool() query()`
- `@mcp.tool() get_schema()`
- `@mcp.tool() get_codebase_overview()`
- `@mcp.tool() analyze_code_structure()`

**Example**:
```python
@mcp.tool()
@requires_initialization
async def query(cypher_query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Existing implementation remains the same
    pass
```

### Step 4: Enhance Initialization
**Action**: Replace existing `initialize()` and background initialization with progress-tracking version

### Step 5: Add Status Tool
**New Tool**:
```python
@mcp.tool()
async def get_server_status() -> Dict[str, Any]:
    """Get current server initialization and health status"""
    global init_state, codebase, kuzu_sync, analyzer

    status = init_state.get_status_dict()
    status.update({
        "components": {
            "codebase": codebase is not None,
            "kuzu_sync": kuzu_sync is not None,
            "analyzer": analyzer is not None
        },
        "configuration": {
            "project_path": str(project_path),
            "db_path": str(db_path),
            "monitoring_enabled": enable_monitoring
        }
    })

    return status
```

## Success Criteria

### Functional Requirements
- [ ] No tool failures during initialization period
- [ ] Clear progress information provided to users
- [ ] Graceful handling of initialization failures
- [ ] Accurate status reporting throughout lifecycle
- [ ] Thread-safe state management

### User Experience Requirements
- [ ] Immediate feedback on server readiness state
- [ ] Progress updates during long initialization
- [ ] Clear error messages for failures
- [ ] Estimated completion times provided
- [ ] No confusing "not initialized" errors

### Technical Requirements
- [ ] Thread-safe state management
- [ ] No race conditions between initialization and tool calls
- [ ] Proper error handling and recovery
- [ ] Minimal performance overhead
- [ ] Clean decorator implementation

## Validation Plan

### Test Scenarios
1. **Immediate Tool Call**: Call tools immediately after server start
2. **During Initialization**: Call tools while initialization in progress
3. **After Completion**: Call tools after successful initialization
4. **Initialization Failure**: Simulate initialization errors
5. **Progress Tracking**: Verify progress updates are accurate

### Testing Commands
```bash
# Start server and immediately test
mcp-client query "MATCH (f:File) RETURN count(f)"

# Monitor status during initialization
mcp-client get_server_status

# Test after completion
mcp-client get_codebase_overview
```

---

**Sub-Task Status**: 📋 SPECIFICATION COMPLETE
**Implementation Priority**: 🔥 HIGH - Must be fixed first
**Estimated Complexity**: 🟡 MEDIUM - Clear solution path
**Dependencies**: None - can be implemented independently