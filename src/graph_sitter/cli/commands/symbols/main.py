from pathlib import Path

import rich
import rich_click as click
from rich.table import Table

from graph_sitter.cli.commands.graph.common import (
    GRAPH_COMMAND_JSON_SCHEMA_VERSION,
    all_symbol_records,
    emit_json,
    graph_options,
    load_codebase,
)


@click.command(name="symbols")
@click.argument("query", required=False, type=str)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--kind", type=click.Choice(["all", "function", "class", "symbol"]), default="all", show_default=True, help="Symbol kind to list.")
@click.option("--max-results", type=click.IntRange(min=1), default=200, show_default=True, help="Maximum symbols to print.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@graph_options
def symbols_command(
    query: str | None,
    path: Path,
    kind: str,
    max_results: int,
    output_format: str,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """List parsed symbols and target strings for graph commands."""
    codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=output_format == "json")
    symbols = all_symbol_records(codebase, query=query, kind=kind, max_results=max_results)
    payload = {
        "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
        "query": query,
        "kind": kind,
        "max_results": max_results,
        "symbols": symbols,
    }

    if output_format == "json":
        emit_json(payload)
        return

    _print_symbols(payload)


def _print_symbols(payload: dict) -> None:
    title = "Graph-sitter symbols"
    if payload.get("query"):
        title = f"{title} {payload['query']}"
    rich.print(f"[bold]{title}[/bold]")
    symbols = payload.get("symbols") or []
    if not symbols:
        rich.print("No symbols found.")
        return

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Target", overflow="fold")
    table.add_column("Kind", overflow="fold")
    table.add_column("Line", justify="right", no_wrap=True)
    table.add_column("Name", overflow="fold")
    for symbol in symbols:
        table.add_row(
            str(symbol.get("target") or ""),
            str(symbol.get("kind") or ""),
            str(symbol.get("line") or ""),
            str(symbol.get("qualified_name") or symbol.get("name") or ""),
        )
    rich.print(table)
