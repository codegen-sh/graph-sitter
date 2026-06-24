from pathlib import Path

import rich_click as click

from graph_sitter.cli.commands.graph.common import (
    GRAPH_COMMAND_JSON_SCHEMA_VERSION,
    emit_json,
    filter_edge_records,
    graph_options,
    load_codebase,
    print_edge_table,
    resolve_target,
    trace_edges,
    trace_filter_options,
)


@click.command(name="usages")
@click.argument("target", type=str)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--depth", type=click.IntRange(min=0), default=1, show_default=True, help="Recursion depth through inbound callers.")
@click.option("--max-results", type=click.IntRange(min=1), default=200, show_default=True, help="Maximum call edges to print.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@trace_filter_options
@graph_options
def usages_command(
    target: str,
    path: Path,
    depth: int,
    max_results: int,
    output_format: str,
    resolved_only: bool,
    local_only: bool,
    hide_runtime: bool,
    dedupe: bool,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Trace call sites that use a target."""
    codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=output_format == "json")
    resolved = resolve_target(codebase, target)
    trace_limit = max_results * 5 if resolved_only or local_only or hide_runtime or dedupe else max_results
    edges = trace_edges(resolved.symbol, direction="inbound", depth=depth, max_results=trace_limit)
    edges = filter_edge_records(edges, resolved_only=resolved_only, local_only=local_only, hide_runtime=hide_runtime, dedupe=dedupe)[:max_results]
    payload = {
        "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
        "direction": "inbound",
        "target": target,
        "depth": depth,
        "max_results": max_results,
        "filters": {
            "resolved_only": resolved_only,
            "local_only": local_only,
            "hide_runtime": hide_runtime,
            "dedupe": dedupe,
        },
        "edges": edges,
    }

    if output_format == "json":
        emit_json(payload)
        return

    print_edge_table("Graph-sitter usages", target, edges, inbound=True)
