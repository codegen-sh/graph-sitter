"""Self-analysis of the graph-sitter codebase using KuzuDB."""

import os
import signal
import sys
import time
from pathlib import Path

from graph_sitter.core.codebase import Codebase
from graph_sitter.shared.logging.get_logger import get_logger
from .sync import KuzuSync
from .monitor import CodeMonitor, CodeGraphAnalyzer

logger = get_logger(__name__)


def analyze_graph_sitter_codebase(
    project_path: str = "./",
    db_path: str = "./graph_sitter_analysis.kuzu",
    with_monitoring: bool = False
):
    """Analyze the graph-sitter codebase itself using the KuzuDB extension."""

    logger.info("Starting graph-sitter self-analysis")

    # Initialize codebase
    codebase = Codebase(project_path)
    logger.info(f"Loaded codebase with {len(codebase.files)} files")

    # Initialize KuzuDB sync
    kuzu_sync = KuzuSync(codebase, db_path)

    try:
        # Perform full sync
        logger.info("Performing full sync to KuzuDB...")
        kuzu_sync.sync_full()

        # Get basic stats
        stats = kuzu_sync.get_stats()
        logger.info(f"Sync completed - {stats}")

        # Initialize analyzer
        analyzer = CodeGraphAnalyzer(kuzu_sync)

        # Perform various analyses
        print("\n" + "="*60)
        print("GRAPH-SITTER CODEBASE ANALYSIS")
        print("="*60)

        # Basic overview
        print("\n1. CODEBASE OVERVIEW")
        print("-" * 30)
        overview = analyzer.get_codebase_overview()
        if overview.has_next():
            row = overview.get_next()
            print(f"Total Files: {row[0]}")
            print(f"Total Functions: {row[1]}")
            print(f"Total Classes: {row[2]}")
            print(f"Total Size: {row[3]:,} bytes")
            print(f"Average Function Complexity: {row[4]:.2f}" if row[4] else "N/A")

        # Complex functions
        print("\n2. MOST COMPLEX FUNCTIONS")
        print("-" * 30)
        complex_funcs = analyzer.find_complex_functions(threshold=5)
        count = 0
        while complex_funcs.has_next() and count < 10:
            row = complex_funcs.get_next()
            print(f"  {row[0]} ({row[1]}:{row[3]}) - Complexity: {row[2]}")
            count += 1

        # Large classes
        print("\n3. CLASSES WITH MOST METHODS")
        print("-" * 30)
        large_classes = analyzer.find_large_classes(threshold=5)
        count = 0
        while large_classes.has_next() and count < 10:
            row = large_classes.get_next()
            print(f"  {row[0]} ({row[1]}:{row[3]}) - Methods: {row[2]}")
            count += 1

        # Unused functions
        print("\n4. POTENTIALLY UNUSED FUNCTIONS")
        print("-" * 30)
        unused_funcs = analyzer.find_unused_functions()
        count = 0
        while unused_funcs.has_next() and count < 10:
            row = unused_funcs.get_next()
            print(f"  {row[0]} ({row[1]}:{row[2]})")
            count += 1

        # Function call chains
        print("\n5. LONGEST FUNCTION CALL CHAINS")
        print("-" * 30)
        call_chains = analyzer.find_function_call_chains(max_depth=4)
        count = 0
        while call_chains.has_next() and count < 5:
            row = call_chains.get_next()
            print(f"  {row[0]} -> {row[1]} (Length: {row[2]})")
            print(f"    Path: {' -> '.join(row[3])}")
            count += 1

        # Core module dependencies
        print("\n6. CORE MODULE USAGE")
        print("-" * 30)
        core_imports = analyzer.find_import_dependencies("graph_sitter.core")
        import_counts = {}
        while core_imports.has_next():
            row = core_imports.get_next()
            module = row[1]
            import_counts[module] = import_counts.get(module, 0) + 1

        for module, count in sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {module}: {count} imports")

        print("\n" + "="*60)

        # Start monitoring if requested
        if with_monitoring:
            print("\nStarting real-time monitoring...")
            print("Press Ctrl+C to stop monitoring\n")

            def on_file_update(file_path: str, change_type: str):
                print(f"[{time.strftime('%H:%M:%S')}] {change_type.upper()}: {file_path}")

            monitor = CodeMonitor(
                codebase=codebase,
                kuzu_sync=kuzu_sync,
                watch_paths=[project_path],
                debounce_delay=0.5
            )
            monitor.add_update_callback(on_file_update)

            def signal_handler(sig, frame):
                print("\nStopping monitor...")
                monitor.stop_monitoring()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            try:
                monitor.start_monitoring()
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                monitor.stop_monitoring()

    finally:
        kuzu_sync.close()


def main():
    """Main entry point for self-analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze graph-sitter codebase with KuzuDB")
    parser.add_argument(
        "--project-path",
        default="./",
        help="Path to the graph-sitter project (default: current directory)"
    )
    parser.add_argument(
        "--db-path",
        default="./graph_sitter_analysis.kuzu",
        help="Path for KuzuDB database (default: ./graph_sitter_analysis.kuzu)"
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Enable real-time file monitoring after analysis"
    )

    args = parser.parse_args()

    analyze_graph_sitter_codebase(
        project_path=args.project_path,
        db_path=args.db_path,
        with_monitoring=args.monitor
    )


if __name__ == "__main__":
    main()