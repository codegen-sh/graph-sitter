from pathlib import Path
from typing import Any

import rich
import rich_click as click
from rich.table import Table

from graph_sitter.cli.commands.graph.common import (
    GRAPH_COMMAND_JSON_SCHEMA_VERSION,
    emit_json,
    graph_options,
    load_codebase,
    resolve_target,
    trace_edges,
)


@click.command(name="usages")
@click.argument("target", type=str)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--depth", type=click.IntRange(min=0), default=1, show_default=True, help="Recursion depth through inbound callers.")
@click.option("--max-results", type=click.IntRange(min=1), default=200, show_default=True, help="Maximum call edges to print.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@graph_options
def usages_command(
    target: str,
    path: Path,
    depth: int,
    max_results: int,
    output_format: str,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Trace call sites that use a target."""
    codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=output_format == "json")
    resolved = resolve_target(codebase, target)
    edges = trace_edges(resolved.symbol, direction="inbound", depth=depth, max_results=max_results)
    payload = {
        "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
        "direction": "inbound",
        "target": target,
        "depth": depth,
        "max_results": max_results,
        "edges": edges,
    }

    if output_format == "json":
        emit_json(payload)
        return

    _print_edges("Graph-sitter usages", target, edges)


def _print_edges(title: str, target: str, edges: list[dict[str, Any]]) -> None:
    rich.print(f"[bold]{title}[/bold] {target}")
    if not edges:
        rich.print("No inbound call edges found.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Depth", justify="right")
    table.add_column("Caller")
    table.add_column("Target")
    table.add_column("Call")
    table.add_column("Location")
    for edge in edges:
        source = edge.get("source") or {}
        target_record = edge.get("target") or {}
        call = edge.get("call") or {}
        table.add_row(
            str(edge.get("depth", "")),
            str(source.get("qualified_name") or source.get("name") or source.get("file") or ""),
            str(target_record.get("qualified_name") or target_record.get("name") or ""),
            str(call.get("name") or ""),
            str(call.get("location") or ""),
        )
    rich.print(table)
