# Project 04.04: Error Recovery & System Resilience

## Sub-Task Overview

**Parent Project**: Project 04 - MCP Self-Inspection Implementation Fixes
**Priority**: 🟡 MEDIUM PRIORITY - System reliability and user experience
**Complexity**: 🟢 LOW-MEDIUM - Focused error handling improvements

## Problem Definition

### Current Error Handling Gaps

**1. Limited Error Recovery**
- No retry mechanisms for transient failures
- Database connection errors cause complete server failure
- File processing errors stop entire synchronization
- No graceful degradation when components fail

**2. Poor Error Communication**
- Generic error messages without actionable information
- Stack traces exposed to MCP clients
- No error classification or severity levels
- Missing context about operation being performed

**3. System State Inconsistencies**
- Partial synchronization states not handled
- Database transactions not properly scoped
- Memory leaks during error conditions
- Resource cleanup not guaranteed

### Error Scenarios to Address

**1. Initialization Failures**
```python
# Current: Server crashes or becomes unusable
try:
    codebase = Codebase(project_path)
except Exception as e:
    # Server becomes unresponsive, no recovery possible
    raise
```

**2. Database Connection Issues**
```python
# Current: All operations fail with cryptic errors
try:
    result = kuzu_sync.query("MATCH (f:File) RETURN count(f)")
except Exception as e:
    # Generic error, no guidance for resolution
    return _error_response(e)
```

**3. File Processing Failures**
```python
# Current: One bad file stops entire sync
for file in codebase.files:
    parse_and_sync(file)  # If this fails, sync stops
```

## Technical Solution

### Error Classification System

**1. Error Categories**
```python
from enum import Enum
from typing import Optional, Dict, Any

class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    INITIALIZATION = "initialization"
    DATABASE = "database"
    FILE_PROCESSING = "file_processing"
    QUERY_EXECUTION = "query_execution"
    CONFIGURATION = "configuration"
    SYSTEM_RESOURCE = "system_resource"

class GraphSitterError(Exception):
    """Base exception for graph-sitter operations"""
    def __init__(self, message: str, category: ErrorCategory, severity: ErrorSeverity,
                 context: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.cause = cause
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
            "timestamp": self.timestamp
        }

class DatabaseError(GraphSitterError):
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.DATABASE, ErrorSeverity.ERROR, **kwargs)
        if query:
            self.context["query"] = query

class FileProcessingError(GraphSitterError):
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.FILE_PROCESSING, ErrorSeverity.WARNING, **kwargs)
        if file_path:
            self.context["file_path"] = file_path
```

### Retry and Recovery Mechanisms

**2. Retry Strategy Implementation**
```python
import time
from functools import wraps
from typing import Callable, Type, Tuple

def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Decorator for retry logic with exponential backoff"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")

            raise last_exception

        return wrapper
    return decorator

# Database operation retry
@retry_on_failure(
    max_attempts=3,
    delay=0.5,
    exceptions=(DatabaseError, ConnectionError)
)
def execute_query_with_retry(query: str, parameters: Dict = None):
    """Execute database query with retry logic"""
    try:
        return kuzu_sync.query(query, parameters or {})
    except Exception as e:
        raise DatabaseError(f"Query execution failed: {e}", query=query, cause=e)
```

### Enhanced Error Response System

**3. Comprehensive Error Responses**
```python
def create_error_response(error: Exception, operation_context: str = "") -> Dict[str, Any]:
    """Create comprehensive error response for MCP clients"""

    if isinstance(error, GraphSitterError):
        # Structured error with context
        response = {
            "status": "error",
            "error": error.to_dict(),
            "operation": operation_context,
            "timestamp": time.time()
        }

        # Add resolution hints based on error category
        response["resolution_hints"] = get_resolution_hints(error)

    else:
        # Generic exception
        response = {
            "status": "error",
            "error": {
                "message": str(error),
                "type": type(error).__name__,
                "category": "unknown",
                "severity": "error"
            },
            "operation": operation_context,
            "timestamp": time.time(),
            "resolution_hints": ["Check server logs for detailed error information"]
        }

    return response

def get_resolution_hints(error: GraphSitterError) -> List[str]:
    """Provide actionable resolution hints based on error category"""
    hints = []

    if error.category == ErrorCategory.DATABASE:
        hints.extend([
            "Check if KuzuDB database file is accessible and not corrupted",
            "Verify database schema is properly initialized",
            "Consider running database repair or reinitialization"
        ])
    elif error.category == ErrorCategory.INITIALIZATION:
        hints.extend([
            "Verify project path exists and is readable",
            "Check available memory and disk space",
            "Review server configuration parameters"
        ])
    elif error.category == ErrorCategory.FILE_PROCESSING:
        hints.extend([
            "Check if file is accessible and has valid syntax",
            "Review file encoding and format",
            "Consider excluding problematic files from processing"
        ])
    elif error.category == ErrorCategory.CONFIGURATION:
        hints.extend([
            "Review server configuration parameters",
            "Check file permissions and paths",
            "Verify required dependencies are installed"
        ])

    return hints
```

### Resilient Operations Implementation

**4. Database Transaction Management**
```python
from contextlib import contextmanager

@contextmanager
def safe_transaction(connection):
    """Safe database transaction with automatic rollback"""
    try:
        connection.execute("BEGIN TRANSACTION")
        yield connection
        connection.execute("COMMIT")
        logger.debug("Transaction committed successfully")
    except Exception as e:
        try:
            connection.execute("ROLLBACK")
            logger.warning(f"Transaction rolled back due to error: {e}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction: {rollback_error}")
        raise DatabaseError("Transaction failed", cause=e)

def sync_file_with_resilience(file_obj) -> Dict[str, Any]:
    """Sync single file with comprehensive error handling"""
    file_path = str(file_obj.filepath)
    operation_result = {
        "file_path": file_path,
        "status": "unknown",
        "errors": [],
        "warnings": []
    }

    try:
        with safe_transaction(kuzu_sync.conn):
            # Parse file
            try:
                parsed_data = parse_file(file_obj)
                operation_result["parsed_entities"] = len(parsed_data.get("functions", []))
            except Exception as e:
                raise FileProcessingError(
                    f"Failed to parse file: {e}",
                    file_path=file_path,
                    cause=e
                )

            # Sync to database
            try:
                sync_parsed_data(file_path, parsed_data)
                operation_result["status"] = "success"
            except Exception as e:
                raise DatabaseError(
                    f"Failed to sync parsed data: {e}",
                    context={"file_path": file_path},
                    cause=e
                )

    except FileProcessingError as e:
        operation_result["status"] = "skipped"
        operation_result["errors"].append(e.to_dict())
        logger.warning(f"Skipping file due to processing error: {file_path}: {e}")

    except DatabaseError as e:
        operation_result["status"] = "failed"
        operation_result["errors"].append(e.to_dict())
        logger.error(f"Database error processing file {file_path}: {e}")

    except Exception as e:
        operation_result["status"] = "failed"
        error = GraphSitterError(
            f"Unexpected error processing file: {e}",
            ErrorCategory.FILE_PROCESSING,
            ErrorSeverity.ERROR,
            context={"file_path": file_path},
            cause=e
        )
        operation_result["errors"].append(error.to_dict())
        logger.error(f"Unexpected error processing {file_path}: {e}")

    return operation_result
```

### System Health Monitoring

**5. Health Check and Recovery**
```python
class SystemHealthMonitor:
    def __init__(self):
        self.last_health_check = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5

    def check_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        health_status = {
            "timestamp": time.time(),
            "overall_status": "unknown",
            "components": {},
            "issues": [],
            "recommendations": []
        }

        # Check database connectivity
        try:
            with safe_transaction(kuzu_sync.conn):
                result = kuzu_sync.conn.execute("MATCH (n) RETURN count(n) LIMIT 1")
                health_status["components"]["database"] = {
                    "status": "healthy",
                    "response_time_ms": "< 10ms"
                }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["issues"].append("Database connectivity issues")

        # Check memory usage
        import psutil
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 90:
            health_status["components"]["memory"] = {
                "status": "warning",
                "usage_percent": memory_usage
            }
            health_status["issues"].append(f"High memory usage: {memory_usage}%")
            health_status["recommendations"].append("Consider restarting server or increasing memory")

        # Check disk space
        disk_usage = psutil.disk_usage('.').percent
        if disk_usage > 95:
            health_status["components"]["disk"] = {
                "status": "critical",
                "usage_percent": disk_usage
            }
            health_status["issues"].append(f"Critical disk space: {disk_usage}%")

        # Overall status determination
        if any(comp.get("status") == "critical" for comp in health_status["components"].values()):
            health_status["overall_status"] = "critical"
        elif any(comp.get("status") == "unhealthy" for comp in health_status["components"].values()):
            health_status["overall_status"] = "unhealthy"
        elif any(comp.get("status") == "warning" for comp in health_status["components"].values()):
            health_status["overall_status"] = "warning"
        else:
            health_status["overall_status"] = "healthy"

        self.last_health_check = health_status
        return health_status

    def attempt_recovery(self, issue_type: str) -> bool:
        """Attempt automatic recovery for known issues"""
        if issue_type == "database_connection":
            try:
                # Attempt database reconnection
                kuzu_sync.reconnect()
                logger.info("Database reconnection successful")
                return True
            except Exception as e:
                logger.error(f"Database reconnection failed: {e}")
                return False

        elif issue_type == "memory_pressure":
            # Trigger garbage collection
            import gc
            gc.collect()
            logger.info("Triggered garbage collection for memory pressure")
            return True

        return False
```

## Implementation Steps

### Step 1: Add Error Classification System
**Location**: `src/graph_sitter/extensions/kuzu_map/`
**Create**: New file `errors.py` with error classes and categories
**Update**: Import error classes in main MCP server file

### Step 2: Implement Retry Mechanisms
**Location**: `kuzu_map_mcp.py`
**Add**: Retry decorators and apply to database operations
**Update**: Query execution methods to use retry logic

### Step 3: Enhanced Error Responses
**Location**: `kuzu_map_mcp.py`
**Replace**: Simple `_error_response()` with comprehensive error handling
**Update**: All MCP tools to use new error response system

### Step 4: Resilient Operations
**Location**: `sync.py`
**Update**: File synchronization with error recovery
**Add**: Transaction management and batch processing resilience

### Step 5: Health Monitoring
**Location**: `kuzu_map_mcp.py`
**Add**: Health check tool and automatic recovery mechanisms
**Integrate**: Health monitoring into server lifecycle

## Implementation Priority

### Phase 1: Core Error Handling (High Priority)
1. Error classification system
2. Enhanced error responses for MCP tools
3. Basic retry mechanisms for database operations

### Phase 2: Resilient Operations (Medium Priority)
1. Safe transaction management
2. File processing error recovery
3. Batch operation resilience

### Phase 3: System Monitoring (Low Priority)
1. Health check implementation
2. Automatic recovery mechanisms
3. Performance monitoring integration

## Success Criteria

### Error Handling Quality
- [ ] All errors provide actionable resolution hints
- [ ] No stack traces exposed to MCP clients
- [ ] Errors categorized by severity and type
- [ ] Context information included in error responses

### System Resilience
- [ ] Individual file processing failures don't stop sync
- [ ] Database connection issues handled gracefully
- [ ] Automatic retry for transient failures
- [ ] Safe transaction rollback on errors

### User Experience
- [ ] Clear error messages with resolution guidance
- [ ] Server remains responsive during error conditions
- [ ] Health status available for monitoring
- [ ] Graceful degradation when components fail

## Validation Plan

### Error Scenario Testing
```bash
# Test database connection failure recovery
# (Simulate by moving database file during operation)

# Test file processing error handling
# (Include malformed files in codebase)

# Test memory pressure handling
# (Process very large codebase)

# Test health monitoring
mcp-client get_server_status
```

### Error Response Validation
```bash
# Test error response format
mcp-client query "INVALID CYPHER SYNTAX"

# Test retry mechanism
# (Simulate temporary database lock)

# Test initialization error handling
# (Start server with invalid project path)
```

---

**Sub-Task Status**: 📋 SPECIFICATION COMPLETE
**Implementation Priority**: 🟡 MEDIUM - Improves reliability and user experience
**Estimated Complexity**: 🟢 LOW-MEDIUM - Focused improvements with clear patterns
**Dependencies**: Can be implemented after core fixes (04.01, 04.02) or in parallel