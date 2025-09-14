"""CLI interface for KuzuDB integration."""

import time
import click
from pathlib import Path

from graph_sitter.core.codebase import Codebase
from graph_sitter.shared.logging.get_logger import get_logger
from .sync import KuzuSync
from .monitor import CodeMonitor, CodeGraphAnalyzer

logger = get_logger(__name__)


@click.group()
def kuzu():
    """KuzuDB integration commands for graph-sitter."""
    pass


@kuzu.command()
@click.option('--project-path', default='./', help='Path to project directory')
@click.option('--db-path', default='./code_graph.kuzu', help='Path to KuzuDB database')
@click.option('--force', is_flag=True, help='Force full resync even if database exists')
def sync(project_path: str, db_path: str, force: bool):
    """Sync codebase to KuzuDB."""
    click.echo(f"Syncing {project_path} to {db_path}")

    codebase = Codebase(project_path)
    kuzu_sync = KuzuSync(codebase, db_path)

    try:
        if force and Path(db_path).exists():
            click.echo("Removing existing database...")
            Path(db_path).unlink()

        start_time = time.time()
        kuzu_sync.sync_full()
        duration = time.time() - start_time

        stats = kuzu_sync.get_stats()
        click.echo(f"Sync completed in {duration:.2f}s")
        click.echo(f"Files: {stats['files']}, Functions: {stats['functions']}, "
                  f"Classes: {stats['classes']}, Imports: {stats['imports']}")

    finally:
        kuzu_sync.close()


@kuzu.command()
@click.option('--project-path', default='./', help='Path to project directory')
@click.option('--db-path', default='./code_graph.kuzu', help='Path to KuzuDB database')
@click.option('--debounce', default=0.5, help='Debounce delay in seconds')
def monitor(project_path: str, db_path: str, debounce: float):
    """Start real-time file monitoring."""
    click.echo(f"Starting monitor for {project_path}")

    codebase = Codebase(project_path)
    kuzu_sync = KuzuSync(codebase, db_path)

    try:
        # Initial sync if database doesn't exist
        if not Path(db_path).exists():
            click.echo("Database not found, performing initial sync...")
            kuzu_sync.sync_full()

        def on_change(file_path: str, change_type: str):
            timestamp = time.strftime('%H:%M:%S')
            click.echo(f"[{timestamp}] {change_type.upper()}: {file_path}")

        monitor = CodeMonitor(
            codebase=codebase,
            kuzu_sync=kuzu_sync,
            debounce_delay=debounce
        )
        monitor.add_update_callback(on_change)

        click.echo("Press Ctrl+C to stop monitoring")

        try:
            with monitor:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\nStopping monitor...")

    finally:
        kuzu_sync.close()


@kuzu.command()
@click.option('--project-path', default='./', help='Path to project directory')
@click.option('--db-path', default='./code_graph.kuzu', help='Path to KuzuDB database')
@click.option('--complexity-threshold', default=10, help='Complexity threshold for analysis')
def analyze(project_path: str, db_path: str, complexity_threshold: int):
    """Analyze codebase using KuzuDB queries."""
    if not Path(db_path).exists():
        click.echo(f"Database not found at {db_path}. Run 'kuzu sync' first.")
        return

    codebase = Codebase(project_path)
    kuzu_sync = KuzuSync(codebase, db_path)

    try:
        analyzer = CodeGraphAnalyzer(kuzu_sync)

        # Codebase overview
        click.echo("CODEBASE OVERVIEW")
        click.echo("=" * 40)
        overview = analyzer.get_codebase_overview()
        if overview.has_next():
            row = overview.get_next()
            click.echo(f"Files: {row[0]}")
            click.echo(f"Functions: {row[1]}")
            click.echo(f"Classes: {row[2]}")
            click.echo(f"Total size: {row[3]:,} bytes")
            if row[4]:
                click.echo(f"Avg function complexity: {row[4]:.2f}")

        # Complex functions
        click.echo(f"\nCOMPLEX FUNCTIONS (threshold: {complexity_threshold})")
        click.echo("-" * 40)
        complex_funcs = analyzer.find_complex_functions(threshold=complexity_threshold)
        count = 0
        while complex_funcs.has_next() and count < 10:
            row = complex_funcs.get_next()
            click.echo(f"  {row[0]} (complexity: {row[2]}) - {row[1]}:{row[3]}")
            count += 1

        if count == 0:
            click.echo("  No functions found above threshold")

        # Unused functions
        click.echo("\nPOTENTIALLY UNUSED FUNCTIONS")
        click.echo("-" * 40)
        unused = analyzer.find_unused_functions()
        count = 0
        while unused.has_next() and count < 10:
            row = unused.get_next()
            click.echo(f"  {row[0]} - {row[1]}:{row[2]}")
            count += 1

        if count == 0:
            click.echo("  No unused functions found")

    finally:
        kuzu_sync.close()


@kuzu.command()
@click.option('--db-path', default='./code_graph.kuzu', help='Path to KuzuDB database')
@click.argument('query')
def query(db_path: str, query: str):
    """Execute a custom Cypher query."""
    if not Path(db_path).exists():
        click.echo(f"Database not found at {db_path}. Run 'kuzu sync' first.")
        return

    # Create a minimal codebase for KuzuSync
    codebase = Codebase("./")
    kuzu_sync = KuzuSync(codebase, db_path)

    try:
        click.echo(f"Executing query: {query}")
        click.echo("-" * 40)

        result = kuzu_sync.query(query)
        count = 0
        while result.has_next():
            row = result.get_next()
            click.echo(f"  {row}")
            count += 1

        click.echo(f"\nReturned {count} rows")

    except Exception as e:
        click.echo(f"Query failed: {e}")

    finally:
        kuzu_sync.close()


@kuzu.command()
@click.option('--db-path', default='./code_graph.kuzu', help='Path to KuzuDB database')
def stats(db_path: str):
    """Show database statistics."""
    if not Path(db_path).exists():
        click.echo(f"Database not found at {db_path}")
        return

    codebase = Codebase("./")
    kuzu_sync = KuzuSync(codebase, db_path)

    try:
        stats = kuzu_sync.get_stats()
        click.echo("DATABASE STATISTICS")
        click.echo("=" * 30)
        for key, value in stats.items():
            click.echo(f"{key.replace('_', ' ').title()}: {value:,}")

    finally:
        kuzu_sync.close()


if __name__ == '__main__':
    kuzu()