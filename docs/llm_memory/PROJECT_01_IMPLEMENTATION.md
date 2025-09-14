# KuzuDB Integration Extension for Graph-Sitter

This extension provides real-time synchronization between graph-sitter's in-memory code graph and KuzuDB, an embedded graph database. It enables powerful graph queries on codebases and real-time monitoring of code changes.

## Features

- **Real-time Sync**: Synchronizes graph-sitter's code graph to KuzuDB
- **File Monitoring**: Uses `watchfiles` for real-time file change detection
- **Graph Queries**: Execute Cypher queries on your codebase structure
- **Self-Analysis**: Analyze the graph-sitter codebase itself
- **CLI Interface**: Command-line tools for easy interaction

## Architecture

The extension follows graph-sitter's coding guidelines with a clean, direct architecture:

- `sync.py`: Core KuzuDB synchronization functionality
- `monitor.py`: Real-time file monitoring with debouncing
- `self_analyze.py`: Self-analysis script for graph-sitter codebase
- `cli.py`: Command-line interface
- `example.py`: Usage examples

## Schema

The KuzuDB schema includes:

### Node Types
- **File**: Source files with metadata (path, size, hash, language)
- **Function**: Functions/methods with complexity metrics
- **Class**: Class definitions with method counts
- **Import**: Import statements with module information

### Relationship Types
- **CONTAINS_FUNCTION**: File → Function
- **CONTAINS_CLASS**: File → Class
- **CONTAINS_IMPORT**: File → Import
- **CLASS_METHOD**: Class → Function
- **FUNCTION_CALLS**: Function → Function
- **INHERITS**: Class → Class

## Quick Start

### 1. Installation

The extension is included with graph-sitter. KuzuDB is added as a dependency in `pyproject.toml`.

### 2. Basic Usage

```python
from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.kuzu_map import KuzuSync, CodeMonitor

# Initialize codebase and sync
codebase = Codebase("./my_project")
kuzu_sync = KuzuSync(codebase, "my_project.kuzu")

# Perform full sync
kuzu_sync.sync_full()

# Get statistics
stats = kuzu_sync.get_stats()
print(f"Synced {stats['functions']} functions, {stats['classes']} classes")
```

### 3. Real-time Monitoring

```python
from graph_sitter.extensions.kuzu_map.monitor import CodeMonitor

def on_change(file_path, change_type):
    print(f"File {change_type}: {file_path}")

monitor = CodeMonitor(codebase, kuzu_sync)
monitor.add_update_callback(on_change)

with monitor:
    # Monitor runs until interrupted
    input("Press Enter to stop...")
```

### 4. Graph Analysis

```python
from graph_sitter.extensions.kuzu_map.monitor import CodeGraphAnalyzer

analyzer = CodeGraphAnalyzer(kuzu_sync)

# Find complex functions
complex_funcs = analyzer.find_complex_functions(threshold=10)

# Find unused functions
unused_funcs = analyzer.find_unused_functions()

# Get codebase overview
overview = analyzer.get_codebase_overview()
```

## CLI Usage

The extension provides a command-line interface:

```bash
# Sync codebase to KuzuDB
python -m src.graph_sitter.extensions.kuzu_map.cli sync --project-path ./

# Start real-time monitoring
python -m src.graph_sitter.extensions.kuzu_map.cli monitor

# Analyze codebase
python -m src.graph_sitter.extensions.kuzu_map.cli analyze

# Execute custom Cypher query
python -m src.graph_sitter.extensions.kuzu_map.cli query "MATCH (f:Function) WHERE f.complexity > 5 RETURN f.name, f.complexity"

# Show database statistics
python -m src.graph_sitter.extensions.kuzu_map.cli stats
```

## Self-Analysis

Run analysis on the graph-sitter codebase itself:

```bash
python -m src.graph_sitter.extensions.kuzu_map.self_analyze --project-path ./ --db-path ./graph_sitter_analysis.kuzu

# With real-time monitoring
python -m src.graph_sitter.extensions.kuzu_map.self_analyze --monitor
```

## Example Queries

### Find High Complexity Functions
```cypher
MATCH (f:Function)
WHERE f.complexity > 10
RETURN f.name, f.file_path, f.complexity
ORDER BY f.complexity DESC
```

### Find Files Importing Specific Modules
```cypher
MATCH (file:File)-[:CONTAINS_IMPORT]->(imp:Import)
WHERE imp.module_name CONTAINS 'pandas'
RETURN file.path, imp.module_name
```

### Find Function Call Chains
```cypher
MATCH path = (start:Function)-[:FUNCTION_CALLS*1..3]->(end:Function)
WHERE start <> end
RETURN [node in nodes(path) | node.name] as call_chain,
       length(path) as chain_length
ORDER BY chain_length DESC
LIMIT 10
```

### Analyze Class Hierarchies
```cypher
MATCH (cls:Class)-[:CLASS_METHOD]->(method:Function)
RETURN cls.name, count(method) as method_count
ORDER BY method_count DESC
```

## Advanced Features

### Custom Event Callbacks

```python
def log_changes(file_path, change_type):
    timestamp = time.strftime('%H:%M:%S')
    print(f"[{timestamp}] {change_type.upper()}: {file_path}")

monitor.add_update_callback(log_changes)
```

### Incremental Updates

```python
# Sync specific file
kuzu_sync.sync_file("path/to/changed_file.py")
```

### Custom Queries with Parameters

```python
result = kuzu_sync.query(
    "MATCH (f:Function) WHERE f.params_count > $threshold RETURN f.name",
    {"threshold": 5}
)
```

## Performance Considerations

- **Debouncing**: File changes are debounced (default 0.5s) to prevent excessive updates
- **Incremental Sync**: Only changed files are re-parsed and synced
- **Transaction Management**: All operations use KuzuDB transactions for consistency
- **Memory Efficient**: Leverages graph-sitter's incremental parsing

## Error Handling

The extension includes comprehensive error handling:

- Automatic transaction rollback on failures
- Graceful handling of missing files
- Robust parameter type conversion
- Detailed logging for debugging

## Integration with Graph-Sitter

This extension follows graph-sitter's architecture principles:

- ✅ No "zero disruption" backwards compatibility
- ✅ No fallbacks or adapters
- ✅ Clean, direct architecture
- ✅ Proper data flow and schema design
- ✅ Lean, organized code structure

The extension integrates seamlessly with graph-sitter's existing codebase analysis capabilities, providing a powerful graph database backend for advanced code analysis workflows.

## Development

To extend the functionality:

1. Add new node/relationship types in `sync.py`
2. Extend analysis functions in `monitor.py`
3. Add CLI commands in `cli.py`
4. Follow the existing patterns for error handling and logging

## Testing

Run the integration test:

```bash
python test_kuzu_integration.py
```

This verifies that the extension loads correctly and can initialize with the graph-sitter codebase.