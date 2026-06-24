from pathlib import Path
from typing import Any

import rich
import rich_click as click
from rich.table import Table

from graph_sitter.cli.commands.graph.common import (
    GRAPH_COMMAND_JSON_SCHEMA_VERSION,
    all_functions_in_file,
    as_list,
    call_record,
    emit_json,
    file_path_of,
    graph_options,
    load_codebase,
    resolve_file,
    safe_attr,
    symbol_record,
)


@click.command(name="inspect")
@click.argument("file", type=str)
@click.argument("path", required=False, type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path("."))
@click.option("--level", type=click.Choice(["summary", "functions", "calls", "full"]), default="functions", show_default=True, help="How much detail to print.")
@click.option("--format", "output_format", type=click.Choice(["summary", "json"]), default="summary", show_default=True, help="Output format.")
@click.option("--max-functions", type=click.IntRange(min=1), default=200, show_default=True, help="Maximum functions to include.")
@click.option("--max-calls", type=click.IntRange(min=0), default=20, show_default=True, help="Maximum call names to include per function.")
@graph_options
def inspect_command(
    file: str,
    path: Path,
    level: str,
    output_format: str,
    max_functions: int,
    max_calls: int,
    backend: str,
    fallback: str,
    language: str,
    subdirectories: tuple[str, ...],
) -> None:
    """Show structure and call stats for a source file."""
    codebase = load_codebase(path, backend, fallback, language, subdirectories, quiet=output_format == "json")
    source_file = resolve_file(codebase, file)
    payload = _file_payload(source_file, level=level, max_functions=max_functions, max_calls=max_calls)

    if output_format == "json":
        emit_json(payload)
        return

    _print_summary(payload)


def _file_payload(source_file: Any, *, level: str, max_functions: int, max_calls: int) -> dict[str, Any]:
    functions = all_functions_in_file(source_file)[:max_functions]
    function_payloads = [_function_payload(function, level=level, max_calls=max_calls) for function in functions]
    source = safe_attr(source_file, "source", "") or ""
    imports = as_list(safe_attr(source_file, "imports"))
    classes = as_list(safe_attr(source_file, "classes"))

    payload: dict[str, Any] = {
        "schema_version": GRAPH_COMMAND_JSON_SCHEMA_VERSION,
        "file": file_path_of(source_file),
        "lines": len(str(source).splitlines()),
        "imports": len(imports),
        "classes": len(classes),
        "functions": len(all_functions_in_file(source_file)),
        "shown_functions": len(function_payloads),
        "level": level,
    }
    if level != "summary":
        payload["function_details"] = function_payloads
    return payload


def _function_payload(function: Any, *, level: str, max_calls: int) -> dict[str, Any]:
    calls = as_list(safe_attr(function, "function_calls"))
    payload = {
        **(symbol_record(function) or {}),
        "calls": len(calls),
    }
    if level in {"calls", "full"}:
        payload["uses"] = [_call_label(call) for call in calls[:max_calls]]
    if level == "full":
        payload["call_details"] = [call_record(call) for call in calls[:max_calls]]
    return payload


def _call_label(call: Any) -> str:
    definitions = as_list(safe_attr(call, "function_definitions"))
    if definitions:
        definition = definitions[0]
        record = symbol_record(definition) or {}
        return str(record.get("qualified_name") or record.get("name") or safe_attr(call, "name", ""))
    return str(safe_attr(call, "name", ""))


def _print_summary(payload: dict[str, Any]) -> None:
    rich.print(f"[bold]Graph-sitter file inspect[/bold] {payload['file']}")
    rich.print(
        "Lines: {lines}  Imports: {imports}  Classes: {classes}  Functions: {functions}".format(
            **payload,
        )
    )
    if payload["level"] == "summary":
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Function")
    table.add_column("Line", justify="right")
    table.add_column("Calls", justify="right")
    if payload["level"] in {"calls", "full"}:
        table.add_column("Uses")

    for function in payload.get("function_details", []):
        row = [
            str(function.get("qualified_name") or function.get("name")),
            str(function.get("line") or ""),
            str(function.get("calls", 0)),
        ]
        if payload["level"] in {"calls", "full"}:
            row.append(", ".join(function.get("uses", [])))
        table.add_row(*row)
    rich.print(table)
