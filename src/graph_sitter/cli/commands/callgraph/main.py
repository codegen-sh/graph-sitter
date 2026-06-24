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
)


@click.command(name="callgraph")
@click.argument("target", type=str)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--direction", type=click.Choice(["outbound", "inbound"]), default="outbound", show_default=True, help="Trace callees or callers.")
@click.option("--depth", type=click.IntRange(min=0), default=2, show_default=True, help="Recursion depth through resolved call edges.")
@click.option("--max-results", type=click.IntRange(min=1), default=200, show_default=True, help="Maximum call edges to print.")
@click.option("--raw", is_flag=True, help="Include unresolved runtime/library calls and repeated call sites.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@graph_options
def callgraph_command(
    target: str,
    path: Path,
    direction: str,
    depth: int,
    max_results: int,
    raw: bool,
    output_format: str,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Trace a clean first-party call graph for a target."""
    codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=output_format == "json")
    resolved = resolve_target(codebase, target)
    trace_limit = max_results if raw else max_results * 5
    edges = trace_edges(resolved.symbol, direction=direction, depth=depth, max_results=trace_limit)
    if not raw:
        edges = filter_edge_records(edges, resolved_only=True, local_only=True, hide_runtime=True, dedupe=True)
    edges = edges[:max_results]
    payload = {
        "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
        "direction": direction,
        "target": target,
        "depth": depth,
        "max_results": max_results,
        "raw": raw,
        "edges": edges,
    }

    if output_format == "json":
        emit_json(payload)
        return

    print_edge_table("Graph-sitter callgraph", target, edges, inbound=direction == "inbound")
