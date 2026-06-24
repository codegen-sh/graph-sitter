import json
import logging
from collections.abc import Callable as CallableType
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rich_click as click

from graph_sitter.cli.commands.parse.main import _parse_language, _project_for_parse, _suppress_parse_logs
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.codebase import Codebase

GRAPH_COMMAND_JSON_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ResolvedTarget:
    raw: str
    file: Any
    symbol: Any


def graph_options(func: CallableType) -> CallableType:
    func = click.option("--subdir", "subdirectories", multiple=True, help="Limit parsing to a repository-relative subdirectory or file. Can be passed more than once.")(func)
    func = click.option("--language", type=click.Choice(["auto", "python", "typescript"]), default="auto", show_default=True, help="Project language.")(func)
    func = click.option("--fallback", type=click.Choice(["python", "error"]), default="python", show_default=True, help="Fallback behavior when the Rust backend is unavailable.")(func)
    func = click.option("--backend", type=click.Choice(["python", "rust", "auto"]), default="python", show_default=True, help="Graph backend to use.")(func)
    return func


def load_codebase(path: Path, backend: str, fallback: str, language: str, subdirectories: tuple[str, ...], *, quiet: bool = True) -> Codebase:
    config = CodebaseConfig(
        graph_backend=GraphBackend(backend),
        rust_fallback=RustFallbackMode(fallback),
    )
    project = _project_for_parse(path.resolve(), _parse_language(language), subdirectories)

    try:
        disabled_level = logging.WARNING if quiet else logging.INFO
        with _suppress_parse_logs(disabled_level):
            return Codebase(projects=[project], config=config)
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error


def emit_json(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, sort_keys=True))


def safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return []


def file_path_of(obj: Any) -> str:
    if obj is None:
        return ""
    if safe_attr(obj, "filepath") is not None:
        return str(safe_attr(obj, "filepath"))
    if safe_attr(obj, "file_path") is not None:
        return str(safe_attr(obj, "file_path"))
    file = safe_attr(obj, "file")
    if file is not None:
        return file_path_of(file)
    return ""


def line_number(obj: Any) -> int | None:
    point = safe_attr(obj, "start_point")
    if point is None:
        return None
    row = safe_attr(point, "row")
    if row is not None:
        return int(row) + 1
    try:
        return int(point[0]) + 1
    except (TypeError, IndexError, ValueError):
        return None


def location_of(obj: Any) -> str:
    path = file_path_of(obj)
    line = line_number(obj)
    if path and line is not None:
        return f"{path}:{line}"
    if path:
        return path
    if line is not None:
        return f":{line}"
    return ""


def symbol_name(symbol: Any) -> str:
    name = safe_attr(symbol, "name")
    if name:
        return str(name)
    return type(symbol).__name__


def qualified_name(symbol: Any) -> str:
    parent_class = safe_attr(symbol, "parent_class")
    if parent_class is not None and safe_attr(parent_class, "name"):
        return f"{parent_class.name}.{symbol_name(symbol)}"
    full_name = safe_attr(symbol, "full_name")
    if full_name:
        return str(full_name)
    return symbol_name(symbol)


def symbol_key(symbol: Any) -> str:
    node_id = safe_attr(symbol, "node_id")
    if node_id is not None:
        return str(node_id)
    return f"{file_path_of(symbol)}:{line_number(symbol)}:{qualified_name(symbol)}:{type(symbol).__name__}"


def symbol_record(symbol: Any | None) -> dict[str, Any] | None:
    if symbol is None:
        return None
    return {
        "name": symbol_name(symbol),
        "qualified_name": qualified_name(symbol),
        "kind": type(symbol).__name__,
        "file": file_path_of(symbol),
        "line": line_number(symbol),
        "location": location_of(symbol),
    }


def call_record(call: Any) -> dict[str, Any]:
    definitions = []
    for definition in as_list(safe_attr(call, "function_definitions")):
        definitions.append(symbol_record(definition))
    return {
        "name": str(safe_attr(call, "name", "")),
        "source": str(safe_attr(call, "source", "")),
        "file": file_path_of(call),
        "line": line_number(call),
        "location": location_of(call),
        "definitions": [definition for definition in definitions if definition is not None],
    }


def all_functions_in_file(source_file: Any) -> list[Any]:
    functions: list[Any] = []
    seen: set[str] = set()

    for function in as_list(safe_attr(source_file, "functions")):
        key = symbol_key(function)
        if key not in seen:
            functions.append(function)
            seen.add(key)

    for class_definition in as_list(safe_attr(source_file, "classes")):
        for method in as_list(safe_attr(class_definition, "methods")):
            key = symbol_key(method)
            if key not in seen:
                functions.append(method)
                seen.add(key)

    return sorted(functions, key=lambda function: line_number(function) or 0)


def resolve_file(codebase: Codebase, file_ref: str) -> Any:
    candidates = _file_ref_candidates(codebase, file_ref)
    for candidate in candidates:
        source_file = codebase.get_file(candidate, optional=True, ignore_case=False)
        if source_file is not None:
            return source_file

    suffix_matches = [source_file for source_file in codebase.files if any(file_path_of(source_file).endswith(candidate) for candidate in candidates)]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    if suffix_matches:
        matches = ", ".join(file_path_of(source_file) for source_file in suffix_matches[:10])
        msg = f"File target is ambiguous: {file_ref}. Matches: {matches}"
        raise click.ClickException(msg)

    msg = f"File not found in parsed codebase: {file_ref}"
    raise click.ClickException(msg)


def resolve_target(codebase: Codebase, raw_target: str) -> ResolvedTarget:
    file_ref, symbol_ref = _split_target(codebase, raw_target)
    if not symbol_ref:
        msg = "Target must include a symbol, for example `src/app.py:handler`."
        raise click.ClickException(msg)

    if file_ref is not None:
        source_file = resolve_file(codebase, file_ref)
        symbol = _resolve_symbol_in_file(source_file, symbol_ref)
        return ResolvedTarget(raw=raw_target, file=source_file, symbol=symbol)

    matches = _global_symbol_matches(codebase, symbol_ref)
    if len(matches) == 1:
        symbol = matches[0]
        return ResolvedTarget(raw=raw_target, file=safe_attr(symbol, "file"), symbol=symbol)
    if matches:
        candidates = ", ".join(_target_label(match) for match in matches[:10])
        msg = f"Symbol target is ambiguous: {symbol_ref}. Matches: {candidates}"
        raise click.ClickException(msg)

    msg = f"Symbol not found in parsed codebase: {symbol_ref}"
    raise click.ClickException(msg)


def caller_for_call(call: Any) -> Any:
    parent_function = safe_attr(call, "parent_function")
    if parent_function is not None:
        return _canonical_function(parent_function, call) or parent_function
    parent_symbol = safe_attr(call, "parent_symbol")
    if parent_symbol is not None:
        return parent_symbol
    return safe_attr(call, "file")


def outbound_edges(symbol: Any) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for call in as_list(safe_attr(symbol, "function_calls")):
        definitions = as_list(safe_attr(call, "function_definitions"))
        if not definitions:
            edges.append({"source": symbol, "target": None, "call": call})
            continue
        for definition in definitions:
            edges.append({"source": symbol, "target": definition, "call": call})
    return edges


def inbound_edges(symbol: Any) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for call in as_list(safe_attr(symbol, "call_sites")):
        edges.append({"source": caller_for_call(call), "target": symbol, "call": call})
    return edges


def edge_record(edge: dict[str, Any], depth: int) -> dict[str, Any]:
    return {
        "depth": depth,
        "source": symbol_record(edge["source"]),
        "target": symbol_record(edge["target"]),
        "call": call_record(edge["call"]),
    }


def trace_edges(symbol: Any, *, direction: str, depth: int, max_results: int) -> list[dict[str, Any]]:
    queue: list[tuple[Any, int]] = [(symbol, 0)]
    visited_nodes = {symbol_key(symbol)}
    seen_edges: set[tuple[str, str, str]] = set()
    records: list[dict[str, Any]] = []

    while queue and len(records) < max_results:
        current, current_depth = queue.pop(0)
        if current_depth >= depth:
            continue

        raw_edges = outbound_edges(current) if direction == "outbound" else inbound_edges(current)
        for edge in raw_edges:
            source_key = symbol_key(edge["source"])
            target_key = symbol_key(edge["target"]) if edge["target"] is not None else f"unresolved:{call_record(edge['call'])['name']}:{location_of(edge['call'])}"
            edge_key = (source_key, target_key, location_of(edge["call"]))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            records.append(edge_record(edge, current_depth + 1))
            if len(records) >= max_results:
                break

            next_symbol = edge["target"] if direction == "outbound" else edge["source"]
            if next_symbol is None:
                continue
            next_key = symbol_key(next_symbol)
            if next_key in visited_nodes:
                continue
            if not as_list(safe_attr(next_symbol, "function_calls")) and not as_list(safe_attr(next_symbol, "call_sites")):
                continue
            visited_nodes.add(next_key)
            queue.append((next_symbol, current_depth + 1))

    return records


def _file_ref_candidates(codebase: Codebase, file_ref: str) -> list[str]:
    raw_path = Path(file_ref).expanduser()
    candidates: list[str] = []
    if raw_path.is_absolute():
        try:
            candidates.append(raw_path.resolve().relative_to(codebase.repo_path.resolve()).as_posix())
        except ValueError:
            candidates.append(raw_path.as_posix())
    else:
        candidates.append(raw_path.as_posix())
    candidates.append(str(file_ref).replace("\\", "/"))
    return list(dict.fromkeys(candidate.removeprefix("./") for candidate in candidates if candidate))


def _split_target(codebase: Codebase, raw_target: str) -> tuple[str | None, str]:
    if "::" in raw_target:
        file_ref, symbol_ref = raw_target.split("::", 1)
        return file_ref, symbol_ref
    if ":" in raw_target:
        file_ref, symbol_ref = raw_target.split(":", 1)
        return file_ref, symbol_ref

    dotted = _split_dotted_file_target(codebase, raw_target)
    if dotted is not None:
        return dotted

    return None, raw_target


def _split_dotted_file_target(codebase: Codebase, raw_target: str) -> tuple[str, str] | None:
    candidates: list[tuple[str, str]] = []
    for source_file in codebase.files:
        filepath = file_path_of(source_file)
        path = Path(filepath)
        variants = [filepath, path.with_suffix("").as_posix()]
        for variant in variants:
            prefix = f"{variant}."
            if raw_target.startswith(prefix):
                candidates.append((filepath, raw_target[len(prefix) :]))
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: len(candidate[0]), reverse=True)
    return candidates[0]


def _resolve_symbol_in_file(source_file: Any, symbol_ref: str) -> Any:
    direct_candidates: list[Any] = []
    get_function = safe_attr(source_file, "get_function")
    if callable(get_function):
        function = get_function(symbol_ref)
        if function is not None:
            direct_candidates.append(function)

    get_symbol = safe_attr(source_file, "get_symbol")
    if callable(get_symbol):
        symbol = get_symbol(symbol_ref)
        if symbol is not None:
            direct_candidates.append(symbol)

    if "." in symbol_ref:
        class_ref, method_ref = symbol_ref.rsplit(".", 1)
        get_class = safe_attr(source_file, "get_class")
        if callable(get_class):
            class_definition = get_class(class_ref)
            get_method = safe_attr(class_definition, "get_method") if class_definition is not None else None
            if callable(get_method):
                method = get_method(method_ref)
                if method is not None:
                    direct_candidates.append(method)

    if direct_candidates:
        return direct_candidates[0]

    matches = [symbol for symbol in _all_symbols_in_file(source_file) if _symbol_matches_ref(symbol, symbol_ref)]
    matches = _dedupe_symbols(matches)
    if len(matches) == 1:
        return matches[0]
    if matches:
        candidates = ", ".join(_target_label(match) for match in matches[:10])
        msg = f"Symbol target is ambiguous in {file_path_of(source_file)}: {symbol_ref}. Matches: {candidates}"
        raise click.ClickException(msg)

    msg = f"Symbol not found in {file_path_of(source_file)}: {symbol_ref}"
    raise click.ClickException(msg)


def _all_symbols_in_file(source_file: Any) -> list[Any]:
    symbols = as_list(safe_attr(source_file, "symbols"))
    for function in all_functions_in_file(source_file):
        symbols.append(function)
    return _dedupe_symbols(symbols)


def _global_symbol_matches(codebase: Codebase, symbol_ref: str) -> list[Any]:
    matches: list[Any] = []
    for source_file in codebase.files:
        for symbol in _all_symbols_in_file(source_file):
            if _symbol_matches_ref(symbol, symbol_ref):
                matches.append(symbol)
    return _dedupe_symbols(matches)


def _symbol_matches_ref(symbol: Any, symbol_ref: str) -> bool:
    return symbol_name(symbol) == symbol_ref or qualified_name(symbol) == symbol_ref or safe_attr(symbol, "full_name") == symbol_ref


def _dedupe_symbols(symbols: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for symbol in symbols:
        key = symbol_key(symbol)
        if key in seen:
            continue
        result.append(symbol)
        seen.add(key)
    return result


def _target_label(symbol: Any) -> str:
    return f"{file_path_of(symbol)}:{qualified_name(symbol)}"


def _canonical_function(function: Any, call: Any) -> Any | None:
    source_file = safe_attr(function, "file") or safe_attr(call, "file")
    if source_file is None:
        return None

    parent_class = safe_attr(function, "parent_class")
    if parent_class is not None and safe_attr(parent_class, "name"):
        get_class = safe_attr(source_file, "get_class")
        class_definition = get_class(parent_class.name) if callable(get_class) else None
        get_method = safe_attr(class_definition, "get_method") if class_definition is not None else None
        method = get_method(symbol_name(function)) if callable(get_method) else None
        if method is not None:
            return method

    get_function = safe_attr(source_file, "get_function")
    if callable(get_function):
        return get_function(symbol_name(function))
    return None
