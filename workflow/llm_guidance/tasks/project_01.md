read workflow/llm_guidance/graph-tree-system-prompt.txt

# BACKGROUND
About https://graph-sitter.com/introduction/overview

I wanted to know :
* is it possible to keep a graph in memory?
* does graph-sitter support "watching" files? How ?
   * if not, can you research if there's a good clean way to do it?
* In case it is possible to keep a graph in memory and update it, is it possible to add a hook/callback/functor to node updates?
* How easy would it be to integrate it with https://docs.kuzudb.com?
   * It has python bindings https://api-docs.kuzudb.com/python/kuzu.html
   * It can be set up locally embedded
   * Works with s-expressions (neo4j alike)
   * has https://docs.kuzudb.com/extensions/attach/sqlite/
   * has https://docs.kuzudb.com/extensions/algo/
* How would a python code with a watchdog updating graph-tree updating kuzu would look like

# DEEPER EXPLORATION

# Graph-sitter and KuzuDB integration for real-time code analysis

## Critical distinction between graph-sitter implementations

The research reveals **two distinct projects** commonly referred to as "graph-sitter": **tree-sitter-graph** (by the tree-sitter organization) and **graph-sitter** (by codegen-sh). Tree-sitter-graph focuses on constructing arbitrary graphs from parsed source code using the Tree-sitter parsing library, while graph-sitter from codegen-sh is built on rustworkx for large-scale codebase manipulation. Both lack native file watching and callback mechanisms, requiring external implementation for real-time updates.

## Memory management capabilities in graph-sitter

Both graph-sitter implementations can maintain graphs in memory with different approaches. **Tree-sitter-graph** provides manual memory control through explicit deletion methods (`ts_tree_delete()`, `ts_parser_delete()`) and supports custom memory allocators via `ts_set_allocator()`. The system shares unchanged tree parts during incremental parsing, optimizing memory usage. However, GitHub issues indicate potential memory scaling concerns with very large graphs.

**Graph-sitter (codegen-sh)** maintains complete codebase graphs connecting functions, classes, and imports in memory using Python's automatic garbage collection. It initializes with `Codebase("./")` to build the complete graph and is designed for handling millions of lines of code. The underlying rustworkx library provides efficient graph algorithm implementations with Python memory management.

For production deployments, memory optimization strategies include implementing LRU caches for parsed AST data, using weak references for cross-file dependencies, and periodic garbage collection of unused graph nodes. Buffer pool configuration in the integration layer helps manage memory allocation between the parsing and database components.

## File watching implementation strategies for Python

Neither graph-sitter variant includes native file watching capabilities, but Python offers robust solutions through the **watchdog library**, which provides cross-platform monitoring with platform-specific optimizations (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows).

### Recommended implementation with watchdog

```python
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
import time
from threading import Timer

class DebouncedGraphHandler(PatternMatchingEventHandler):
    def __init__(self, graph_manager, delay=0.3):
        patterns = ["*.py", "*.js", "*.ts", "*.tsx"]
        super().__init__(patterns=patterns, ignore_directories=True)
        self.graph_manager = graph_manager
        self.delay = delay
        self.timers = {}
        
    def on_modified(self, event):
        # Cancel existing timer for this file
        if event.src_path in self.timers:
            self.timers[event.src_path].cancel()
        
        # Create debounced update
        timer = Timer(self.delay, self._update_graph, args=[event.src_path])
        self.timers[event.src_path] = timer
        timer.start()
    
    def _update_graph(self, file_path):
        try:
            # Parse with tree-sitter
            parsed_data = self.graph_manager.parse_file(file_path)
            # Update in-memory graph
            self.graph_manager.update_graph(file_path, parsed_data)
            # Sync to database
            self.graph_manager.sync_to_database()
        finally:
            self.timers.pop(file_path, None)

# Usage
observer = Observer()
handler = DebouncedGraphHandler(graph_manager)
observer.schedule(handler, path="./src", recursive=True)
observer.start()
```

Alternative high-performance option using **watchfiles** (Rust-based) provides async capabilities:

```python
import asyncio
from watchfiles import awatch

async def monitor_code_changes(graph_manager):
    async for changes in awatch('./src', recursive=True):
        for change_type, file_path in changes:
            if file_path.suffix in {'.py', '.js', '.ts'}:
                await graph_manager.async_update(file_path, change_type)
```

## Implementing hooks and callbacks for graph updates

While graph-sitter lacks built-in event systems, you can implement robust callback mechanisms using the **Publisher-Subscriber pattern**:

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Callable
import threading

class GraphEvent:
    def __init__(self, event_type: str, node_id: str, data: Dict):
        self.event_type = event_type  # 'node_added', 'node_updated', 'node_removed'
        self.node_id = node_id
        self.data = data
        self.timestamp = time.time()

class GraphEventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
    
    def publish(self, event: GraphEvent):
        with self._lock:
            callbacks = self._subscribers.get(event.event_type, [])
        
        for callback in callbacks:
            threading.Thread(target=callback, args=(event,), daemon=True).start()

class GraphManager:
    def __init__(self):
        self.event_bus = GraphEventBus()
        self.graph_data = {}
    
    def update_node(self, node_id: str, new_data: Dict):
        old_data = self.graph_data.get(node_id)
        self.graph_data[node_id] = new_data
        
        # Publish event with hooks
        event = GraphEvent('node_updated', node_id, {
            'old': old_data,
            'new': new_data
        })
        self.event_bus.publish(event)
    
    def add_update_hook(self, callback: Callable):
        self.event_bus.subscribe('node_updated', callback)
```

This pattern enables attaching multiple callbacks to graph operations, supporting use cases like logging changes, triggering analysis pipelines, or updating UI components.

## KuzuDB integration architecture

KuzuDB provides an exceptional embedded graph database solution with **comprehensive Python bindings** that align perfectly with graph-sitter requirements. The database supports both in-memory and persistent storage modes, making it ideal for maintaining synchronized graph representations.

### Key integration capabilities

KuzuDB operates as an embedded database within your Python process, eliminating serialization overhead and providing:
- **Cypher query language** with near-full Neo4j compatibility
- **ACID transactions** with serializable isolation
- **Columnar storage** with vectorized query processing showing up to 188x speedup over Neo4j
- **Multiple output formats** including Pandas, NetworkX, and PyTorch Geometric

### Integration implementation

```python
import kuzu
from typing import Dict, List
import json

class KuzuGraphSync:
    def __init__(self, db_path: str = "./code_graph.kuzu"):
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()
    
    def _initialize_schema(self):
        # Create node tables
        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS File(
                path STRING PRIMARY KEY,
                language STRING,
                last_modified INT64,
                loc INT64
            )
        """)
        
        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Function(
                id STRING PRIMARY KEY,
                name STRING,
                file_path STRING,
                start_line INT64,
                complexity INT64,
                docstring STRING
            )
        """)
        
        # Create relationship tables
        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS CONTAINS(
                FROM File TO Function
            )
        """)
        
        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS CALLS(
                FROM Function TO Function,
                line_number INT64
            )
        """)
    
    def sync_parsed_data(self, file_path: str, parsed_data: Dict):
        """Sync tree-sitter parsed data to KuzuDB"""
        try:
            self.conn.execute("BEGIN TRANSACTION")
            
            # Delete existing data for this file
            self.conn.execute(
                "MATCH (f:File {path: $path})-[r:CONTAINS]->(fn:Function) "
                "DELETE r, fn",
                {"path": file_path}
            )
            
            # Insert or update file node
            self.conn.execute(
                "MERGE (f:File {path: $path}) "
                "SET f.language = $lang, f.last_modified = $modified, f.loc = $loc",
                {
                    "path": file_path,
                    "lang": parsed_data.get("language", "python"),
                    "modified": int(time.time()),
                    "loc": parsed_data.get("lines_of_code", 0)
                }
            )
            
            # Insert functions
            for func in parsed_data.get("functions", []):
                func_id = f"{file_path}::{func['name']}:{func['start_line']}"
                
                self.conn.execute(
                    "CREATE (fn:Function {id: $id, name: $name, "
                    "file_path: $path, start_line: $line, "
                    "complexity: $complexity, docstring: $doc})",
                    {
                        "id": func_id,
                        "name": func["name"],
                        "path": file_path,
                        "line": func["start_line"],
                        "complexity": func.get("complexity", 1),
                        "doc": func.get("docstring", "")
                    }
                )
                
                # Create CONTAINS relationship
                self.conn.execute(
                    "MATCH (f:File {path: $path}), (fn:Function {id: $id}) "
                    "CREATE (f)-[:CONTAINS]->(fn)",
                    {"path": file_path, "id": func_id}
                )
            
            # Create CALLS relationships
            for call in parsed_data.get("function_calls", []):
                self.conn.execute(
                    "MATCH (f1:Function {name: $caller}), (f2:Function {name: $callee}) "
                    "WHERE f1.file_path = $path "
                    "CREATE (f1)-[:CALLS {line_number: $line}]->(f2)",
                    {
                        "caller": call["from_function"],
                        "callee": call["to_function"],
                        "path": file_path,
                        "line": call["line_number"]
                    }
                )
            
            self.conn.execute("COMMIT")
            
        except Exception as e:
            self.conn.execute("ROLLBACK")
            raise e
    
    def query_complex_functions(self, complexity_threshold: int = 10):
        """Find functions with high cyclomatic complexity"""
        result = self.conn.execute(
            "MATCH (f:Function) "
            "WHERE f.complexity > $threshold "
            "RETURN f.name, f.file_path, f.complexity "
            "ORDER BY f.complexity DESC",
            {"threshold": complexity_threshold}
        )
        return result.get_as_df()
```

## Complete example: Watchdog updating graph-sitter and syncing with KuzuDB

```python
import os
import hashlib
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading
import kuzu
from typing import Dict, Optional
import logging

class CodeGraphMonitor:
    """Complete integration of tree-sitter, watchdog, and KuzuDB"""
    
    def __init__(self, project_path: str, db_path: str = "./code_graph.kuzu"):
        self.project_path = Path(project_path)
        self.db_path = db_path
        
        # Initialize tree-sitter
        self.language = Language(tspython.language())
        self.parser = Parser(self.language)
        
        # Initialize KuzuDB
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_database_schema()
        
        # File tracking
        self.file_hashes: Dict[str, str] = {}
        self.lock = threading.RLock()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Event callbacks
        self.update_callbacks = []
    
    def _init_database_schema(self):
        """Initialize KuzuDB schema for code graph"""
        queries = [
            "CREATE NODE TABLE IF NOT EXISTS File(path STRING PRIMARY KEY, "
            "hash STRING, language STRING, last_analyzed INT64, loc INT64)",
            
            "CREATE NODE TABLE IF NOT EXISTS Function(id STRING PRIMARY KEY, "
            "name STRING, file_path STRING, start_line INT64, end_line INT64, "
            "complexity INT64, parameters STRING)",
            
            "CREATE NODE TABLE IF NOT EXISTS Class(id STRING PRIMARY KEY, "
            "name STRING, file_path STRING, start_line INT64)",
            
            "CREATE REL TABLE IF NOT EXISTS CONTAINS_FUNCTION(FROM File TO Function)",
            "CREATE REL TABLE IF NOT EXISTS CONTAINS_CLASS(FROM File TO Class)",
            "CREATE REL TABLE IF NOT EXISTS CALLS(FROM Function TO Function, line INT64)",
            "CREATE REL TABLE IF NOT EXISTS INHERITS(FROM Class TO Class)"
        ]
        
        for query in queries:
            self.conn.execute(query)
    
    def parse_python_file(self, file_path: str) -> Dict:
        """Parse Python file using tree-sitter"""
        with open(file_path, 'rb') as f:
            source_code = f.read()
        
        tree = self.parser.parse(source_code)
        
        return {
            'functions': self._extract_functions(tree.root_node, source_code),
            'classes': self._extract_classes(tree.root_node, source_code),
            'imports': self._extract_imports(tree.root_node, source_code),
            'calls': self._extract_function_calls(tree.root_node, source_code),
            'loc': len(source_code.decode().split('\n'))
        }
    
    def _extract_functions(self, node, source_code) -> list:
        """Extract function definitions from AST"""
        functions = []
        
        def visit(node):
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                params_node = node.child_by_field_name('parameters')
                
                if name_node:
                    func_data = {
                        'name': source_code[name_node.start_byte:name_node.end_byte].decode(),
                        'start_line': node.start_point[0],
                        'end_line': node.end_point[0],
                        'complexity': self._calculate_complexity(node),
                        'parameters': []
                    }
                    
                    if params_node:
                        func_data['parameters'] = self._extract_parameters(params_node, source_code)
                    
                    functions.append(func_data)
            
            for child in node.children:
                visit(child)
        
        visit(node)
        return functions
    
    def _calculate_complexity(self, node) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1
        
        def count_branches(node):
            nonlocal complexity
            if node.type in ['if_statement', 'elif_clause', 'for_statement', 
                             'while_statement', 'except_clause']:
                complexity += 1
            for child in node.children:
                count_branches(child)
        
        count_branches(node)
        return complexity
    
    def update_file_in_graph(self, file_path: str):
        """Update graph for a specific file"""
        try:
            # Calculate file hash
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Check if file has changed
            with self.lock:
                if self.file_hashes.get(file_path) == file_hash:
                    return  # No changes
                self.file_hashes[file_path] = file_hash
            
            # Parse file
            parsed_data = self.parse_python_file(file_path)
            
            # Update database
            self.sync_to_database(file_path, parsed_data, file_hash)
            
            # Trigger callbacks
            for callback in self.update_callbacks:
                callback(file_path, parsed_data)
            
            self.logger.info(f"Updated graph for {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error updating {file_path}: {e}")
    
    def sync_to_database(self, file_path: str, parsed_data: Dict, file_hash: str):
        """Sync parsed data to KuzuDB"""
        rel_path = str(Path(file_path).relative_to(self.project_path))
        
        try:
            self.conn.execute("BEGIN TRANSACTION")
            
            # Clean up old data
            self.conn.execute(
                "MATCH (f:File {path: $path})-[r]-(n) DELETE r",
                {"path": rel_path}
            )
            
            # Update file node
            self.conn.execute(
                "MERGE (f:File {path: $path}) "
                "SET f.hash = $hash, f.language = 'python', "
                "f.last_analyzed = $time, f.loc = $loc",
                {
                    "path": rel_path,
                    "hash": file_hash,
                    "time": int(time.time()),
                    "loc": parsed_data['loc']
                }
            )
            
            # Add functions
            for func in parsed_data['functions']:
                func_id = f"{rel_path}:{func['name']}:{func['start_line']}"
                
                self.conn.execute(
                    "MERGE (fn:Function {id: $id}) "
                    "SET fn.name = $name, fn.file_path = $path, "
                    "fn.start_line = $start, fn.end_line = $end, "
                    "fn.complexity = $complexity, fn.parameters = $params",
                    {
                        "id": func_id,
                        "name": func['name'],
                        "path": rel_path,
                        "start": func['start_line'],
                        "end": func['end_line'],
                        "complexity": func['complexity'],
                        "params": json.dumps(func['parameters'])
                    }
                )
                
                self.conn.execute(
                    "MATCH (f:File {path: $path}), (fn:Function {id: $id}) "
                    "CREATE (f)-[:CONTAINS_FUNCTION]->(fn)",
                    {"path": rel_path, "id": func_id}
                )
            
            self.conn.execute("COMMIT")
            
        except Exception as e:
            self.conn.execute("ROLLBACK")
            raise e
    
    def add_update_callback(self, callback):
        """Add callback for graph updates"""
        self.update_callbacks.append(callback)
    
    def start_monitoring(self):
        """Start file system monitoring"""
        # Initial scan
        for py_file in self.project_path.rglob("*.py"):
            if '.git' not in py_file.parts:
                self.update_file_in_graph(str(py_file))
        
        # Setup watchdog
        event_handler = CodeFileHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.project_path), recursive=True)
        observer.start()
        
        self.logger.info(f"Monitoring {self.project_path}")
        return observer
    
    def query_high_complexity_functions(self, threshold: int = 10):
        """Query functions with high complexity"""
        result = self.conn.execute(
            "MATCH (f:Function) WHERE f.complexity > $threshold "
            "RETURN f.name, f.file_path, f.complexity "
            "ORDER BY f.complexity DESC",
            {"threshold": threshold}
        )
        return result.get_as_df()

class CodeFileHandler(FileSystemEventHandler):
    """Watchdog event handler for code files"""
    
    def __init__(self, monitor: CodeGraphMonitor):
        self.monitor = monitor
        self.debounce_timers = {}
        self.debounce_delay = 0.5
    
    def _debounced_update(self, file_path: str):
        """Debounce file updates"""
        if file_path in self.debounce_timers:
            self.debounce_timers[file_path].cancel()
        
        timer = threading.Timer(
            self.debounce_delay,
            lambda: self.monitor.update_file_in_graph(file_path)
        )
        self.debounce_timers[file_path] = timer
        timer.start()
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self._debounced_update(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            self._debounced_update(event.src_path)

# Usage example
if __name__ == "__main__":
    import signal
    import sys
    
    # Initialize monitor
    monitor = CodeGraphMonitor("./my_project", "./code_graph.kuzu")
    
    # Add callback for updates
    def on_graph_update(file_path, parsed_data):
        print(f"Graph updated for {file_path}")
        print(f"  Functions: {len(parsed_data['functions'])}")
        print(f"  Classes: {len(parsed_data['classes'])}")
    
    monitor.add_update_callback(on_graph_update)
    
    # Start monitoring
    observer = monitor.start_monitoring()
    
    # Query high complexity functions
    complex_funcs = monitor.query_high_complexity_functions(threshold=5)
    print("\nHigh complexity functions:")
    print(complex_funcs)
    
    # Keep running until interrupted
    def signal_handler(sig, frame):
        observer.stop()
        observer.join()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
```

## Production deployment considerations

The integration architecture supports several optimization strategies for production environments. **Incremental parsing** using tree-sitter's edit functionality reduces parsing overhead by reusing unchanged AST portions. **Connection pooling** in KuzuDB's async API enables efficient concurrent reads while respecting the single-writer constraint. **Batch synchronization** accumulates multiple file changes before database updates, reducing transaction overhead.

For error resilience, implement automatic database backups before major operations, health checks monitoring system state, and retry mechanisms with exponential backoff. The debouncing mechanism prevents excessive updates during rapid file changes, while hash-based change detection eliminates redundant parsing operations.

Performance benchmarks show this architecture can handle repositories with millions of lines of code, processing file updates in under 100ms for average-sized files and maintaining sub-second query response times for complex graph traversals. The embedded nature of KuzuDB eliminates network overhead, while tree-sitter's incremental parsing minimizes CPU usage during updates.

# TASK

Research the internet if required
Use graph-sitter on itself
Implement such process in src/graph_sitter/extensions/kuzu_map as an extension of graph-sitter. 

read @.claude/commands/🧠.md