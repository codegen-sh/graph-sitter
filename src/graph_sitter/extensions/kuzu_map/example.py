"""Example usage of the KuzuDB integration extension."""

import time
from graph_sitter.core.codebase import Codebase
from graph_sitter.extensions.kuzu_map import KuzuSync, CodeMonitor
from graph_sitter.extensions.kuzu_map.monitor import CodeGraphAnalyzer


def basic_sync_example():
    """Basic example of syncing a codebase to KuzuDB."""
    print("=== Basic Sync Example ===")

    # Initialize codebase
    codebase = Codebase("./")

    # Initialize KuzuDB sync
    kuzu_sync = KuzuSync(codebase, db_path="./example.kuzu")

    try:
        # Perform full sync
        print("Syncing codebase to KuzuDB...")
        kuzu_sync.sync_full()

        # Get statistics
        stats = kuzu_sync.get_stats()
        print(f"Sync completed: {stats}")

        # Example queries
        print("\nRunning example queries...")

        # Find all Python files
        result = kuzu_sync.query(
            "MATCH (f:File) WHERE f.extension = '.py' RETURN f.path, f.size LIMIT 5"
        )
        print("\nPython files:")
        while result.has_next():
            row = result.get_next()
            print(f"  {row[0]} ({row[1]} bytes)")

        # Find functions with parameters
        result = kuzu_sync.query(
            "MATCH (f:Function) WHERE f.params_count > 3 RETURN f.name, f.params_count LIMIT 5"
        )
        print("\nFunctions with many parameters:")
        while result.has_next():
            row = result.get_next()
            print(f"  {row[0]} ({row[1]} params)")

    finally:
        kuzu_sync.close()


def monitoring_example():
    """Example of real-time file monitoring."""
    print("\n=== Monitoring Example ===")

    # Initialize codebase
    codebase = Codebase("./")
    kuzu_sync = KuzuSync(codebase, db_path="./monitor_example.kuzu")

    try:
        # Initial sync
        kuzu_sync.sync_full()

        # Set up monitoring
        def on_file_change(file_path: str, change_type: str):
            print(f"[{time.strftime('%H:%M:%S')}] File {change_type}: {file_path}")

        monitor = CodeMonitor(
            codebase=codebase,
            kuzu_sync=kuzu_sync,
            debounce_delay=0.3
        )
        monitor.add_update_callback(on_file_change)

        print("Starting file monitoring...")
        print("Try editing a Python file in another terminal")
        print("Press Ctrl+C to stop")

        with monitor:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping monitor...")

    finally:
        kuzu_sync.close()


def analysis_example():
    """Example of code analysis using KuzuDB queries."""
    print("\n=== Analysis Example ===")

    # Initialize
    codebase = Codebase("./")
    kuzu_sync = KuzuSync(codebase, db_path="./analysis_example.kuzu")

    try:
        # Sync data
        kuzu_sync.sync_full()

        # Initialize analyzer
        analyzer = CodeGraphAnalyzer(kuzu_sync)

        # Find complex functions
        print("\nComplex functions:")
        result = analyzer.find_complex_functions(threshold=1)
        count = 0
        while result.has_next() and count < 5:
            row = result.get_next()
            print(f"  {row[0]} (complexity: {row[2]}) in {row[1]}")
            count += 1

        # Find large classes
        print("\nClasses with many methods:")
        result = analyzer.find_large_classes(threshold=1)
        count = 0
        while result.has_next() and count < 5:
            row = result.get_next()
            print(f"  {row[0]} ({row[2]} methods) in {row[1]}")
            count += 1

        # Codebase overview
        print("\nCodebase overview:")
        result = analyzer.get_codebase_overview()
        if result.has_next():
            row = result.get_next()
            print(f"  Files: {row[0]}")
            print(f"  Functions: {row[1]}")
            print(f"  Classes: {row[2]}")
            print(f"  Total size: {row[3]:,} bytes")

    finally:
        kuzu_sync.close()


def custom_query_example():
    """Example of custom Cypher queries."""
    print("\n=== Custom Query Example ===")

    codebase = Codebase("./")
    kuzu_sync = KuzuSync(codebase, db_path="./custom_example.kuzu")

    try:
        kuzu_sync.sync_full()

        # Custom query: Find files that import specific modules
        print("\nFiles importing 'pathlib':")
        result = kuzu_sync.query("""
            MATCH (file:File)-[:CONTAINS_IMPORT]->(imp:Import)
            WHERE imp.module_name CONTAINS 'pathlib'
            RETURN DISTINCT file.path, imp.module_name
            LIMIT 5
        """)

        while result.has_next():
            row = result.get_next()
            print(f"  {row[0]} imports {row[1]}")

        # Custom query: Function call relationships
        print("\nFunction call relationships:")
        result = kuzu_sync.query("""
            MATCH (caller:Function)-[r:FUNCTION_CALLS]->(callee:Function)
            RETURN caller.name, callee.name, r.line_number
            LIMIT 5
        """)

        while result.has_next():
            row = result.get_next()
            print(f"  {row[0]} calls {row[1]} at line {row[2]}")

        # Custom query: Class inheritance
        print("\nClass method relationships:")
        result = kuzu_sync.query("""
            MATCH (cls:Class)-[r:CLASS_METHOD]->(method:Function)
            RETURN cls.name, method.name, r.visibility
            LIMIT 5
        """)

        while result.has_next():
            row = result.get_next()
            print(f"  {row[0]}.{row[1]} ({row[2]})")

    finally:
        kuzu_sync.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "sync":
            basic_sync_example()
        elif example == "monitor":
            monitoring_example()
        elif example == "analyze":
            analysis_example()
        elif example == "query":
            custom_query_example()
        else:
            print(f"Unknown example: {example}")
            print("Available examples: sync, monitor, analyze, query")
    else:
        print("Running all examples...")
        basic_sync_example()
        analysis_example()
        custom_query_example()
        print("\nTo run monitoring example: python example.py monitor")