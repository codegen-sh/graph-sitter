from pathlib import Path
from typing import Any

import rich
import rich_click as click

from graph_sitter.cli.commands.graph.common import (
    GRAPH_COMMAND_JSON_SCHEMA_VERSION,
    as_list,
    emit_json,
    graph_options,
    load_codebase,
    resolve_target,
    safe_attr,
    symbol_record,
)


@click.command(name="rename")
@click.argument("target", type=str)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--to", "new_name", required=True, help="New symbol name.")
@click.option("--check", is_flag=True, help="Preview the resolved target and reference counts without writing. This is the default.")
@click.option("--write", is_flag=True, help="Apply the rename and write changes to disk.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@graph_options
def rename_command(
    target: str,
    path: Path,
    new_name: str,
    check: bool,
    write: bool,
    output_format: str,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Rename a function or symbol across its resolved references."""
    if check and write:
        msg = "--check and --write cannot be used together"
        raise click.ClickException(msg)

    codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=output_format == "json")
    resolved = resolve_target(codebase, target)
    symbol = resolved.symbol
    old_name = str(safe_attr(symbol, "name", target))
    reference_count = len(as_list(safe_attr(symbol, "usages")))
    call_site_count = len(as_list(safe_attr(symbol, "call_sites")))
    applied = bool(write)

    if write:
        rename = safe_attr(symbol, "rename")
        if not callable(rename):
            msg = f"Resolved target cannot be renamed: {target}"
            raise click.ClickException(msg)
        rename(new_name)
        codebase.commit()

    payload = _payload(
        target=target,
        old_name=old_name,
        new_name=new_name,
        symbol=symbol,
        reference_count=reference_count,
        call_site_count=call_site_count,
        applied=applied,
    )

    if output_format == "json":
        emit_json(payload)
        return

    _print_summary(payload)


def _payload(
    *,
    target: str,
    old_name: str,
    new_name: str,
    symbol: Any,
    reference_count: int,
    call_site_count: int,
    applied: bool,
) -> dict[str, Any]:
    return {
        "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
        "target": target,
        "old_name": old_name,
        "new_name": new_name,
        "symbol": symbol_record(symbol),
        "references": reference_count,
        "call_sites": call_site_count,
        "applied": applied,
    }


def _print_summary(payload: dict[str, Any]) -> None:
    symbol = payload.get("symbol") or {}
    mode = "Applied" if payload["applied"] else "Dry run"
    rich.print(f"[bold]Graph-sitter rename[/bold] {mode}")
    rich.print(f"Target: {symbol.get('location') or payload['target']}")
    rich.print(f"Rename: {payload['old_name']} -> {payload['new_name']}")
    rich.print(f"References: {payload['references']}  Call sites: {payload['call_sites']}")
    if not payload["applied"]:
        rich.print("Pass --write to apply this rename.")
