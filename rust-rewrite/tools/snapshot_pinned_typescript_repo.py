#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from benchmark_pinned_typescript_repo import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_EXPECTED_COMMIT,
    DEFAULT_EXTENSION_DIR,
    DEFAULT_REF,
    DEFAULT_REPO_NAME,
    DEFAULT_REPO_URL,
    build_rust_extension,
    prepare_pinned_repo,
)
from measure_typescript_rust_index import discover_typescript_files  # noqa: E402
from snapshot_pinned_python_repo import (  # noqa: E402
    bytes_to_mb,
    compact_record_set,
    compare_snapshot,
    max_rss_bytes,
)

DEFAULT_EXPECTED_SNAPSHOT = (
    REPO_ROOT / "rust-rewrite/golden/next.js-v15.0.0-rust-compact-typescript.json"
)
SNAPSHOT_SCHEMA_VERSION = 4


def range_list(record: dict[str, Any], name: str = "range") -> list[int]:
    source_range = record[name]
    if isinstance(source_range, list):
        return source_range
    return [
        source_range["start_byte"],
        source_range["end_byte"],
        source_range["start_row"],
        source_range["start_column"],
        source_range["end_row"],
        source_range["end_column"],
    ]


def symbol_key(symbol: dict[str, Any], file_by_id: dict[int, dict[str, Any]]) -> str:
    file = file_by_id[symbol["file_id"]]
    return f"{file['path']}:{symbol['kind']}:{symbol['name']}@{range_list(symbol, 'name_range')[0]}"


def import_key(import_record: dict[str, Any], file_by_id: dict[int, dict[str, Any]]) -> str:
    file = file_by_id[import_record["file_id"]]
    module = import_record["module"] or ""
    name = import_record["name"] or ""
    alias = import_record["alias"] or ""
    return f"{file['path']}:{import_record['kind']}:{module}:{name}:{alias}@{range_list(import_record)[0]}"


def import_resolution_key(
    resolution: dict[str, Any],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
) -> str:
    import_record = import_by_id[resolution["import_id"]]
    target_file = file_by_id[resolution["target_file_id"]]["path"]
    target_symbol = (
        ""
        if resolution["target_symbol_id"] is None
        else symbol_key(symbol_by_id[resolution["target_symbol_id"]], file_by_id)
    )
    return f"{import_key(import_record, file_by_id)}->{target_file}:{target_symbol}"


def export_key(export: dict[str, Any], file_by_id: dict[int, dict[str, Any]]) -> str:
    file = file_by_id[export["file_id"]]
    name = export["name"] or ""
    local_name = export["local_name"] or ""
    source_module = export["source_module"] or ""
    return f"{file['path']}:{export['kind']}:{name}:{local_name}:{source_module}@{range_list(export)[0]}"


def reference_key(
    reference: dict[str, Any],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
) -> str:
    source_symbol = (
        ""
        if reference["source_symbol_id"] is None
        else symbol_key(symbol_by_id[reference["source_symbol_id"]], file_by_id)
    )
    import_record = (
        ""
        if reference["import_id"] is None
        else import_key(import_by_id[reference["import_id"]], file_by_id)
    )
    target_symbol = symbol_key(symbol_by_id[reference["target_symbol_id"]], file_by_id)
    source_file = file_by_id[reference["source_file_id"]]["path"]
    return f"{source_file}:{source_symbol}->{target_symbol}:{import_record}:{reference['name']}@{range_list(reference)[0]}"


def subclass_edge_key(
    subclass_edge: dict[str, Any],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
    reference_by_id: dict[int, dict[str, Any]],
) -> str:
    source_symbol = symbol_key(
        symbol_by_id[subclass_edge["source_symbol_id"]], file_by_id
    )
    target_symbol = symbol_key(
        symbol_by_id[subclass_edge["target_symbol_id"]], file_by_id
    )
    reference = reference_key(
        reference_by_id[subclass_edge["reference_id"]],
        file_by_id,
        symbol_by_id,
        import_by_id,
    )
    return f"{source_symbol}->{target_symbol}:{reference}"


def make_file_rows(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "path": file["path"],
            "byte_len": file["byte_len"],
            "line_count": file["line_count"],
            "has_error": file["has_error"],
            "root_range": range_list(file, "root_range"),
        }
        for file in files
    ]
    return sorted(rows, key=lambda row: row["path"])


def make_symbol_rows(
    symbols: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "key": symbol_key(symbol, file_by_id),
            "parent_symbol": None
            if symbol["parent_symbol_id"] is None
            else symbol_key(symbol_by_id[symbol["parent_symbol_id"]], file_by_id),
            "is_top_level": symbol["is_top_level"],
            "file": file_by_id[symbol["file_id"]]["path"],
            "kind": symbol["kind"],
            "name": symbol["name"],
            "range": range_list(symbol),
            "name_range": range_list(symbol, "name_range"),
        }
        for symbol in symbols
    ]
    return sorted(
        rows,
        key=lambda row: (row["file"], row["kind"], row["name"], row["name_range"]),
    )


def make_import_rows(
    imports: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "key": import_key(import_record, file_by_id),
            "file": file_by_id[import_record["file_id"]]["path"],
            "kind": import_record["kind"],
            "module": import_record["module"],
            "name": import_record["name"],
            "alias": import_record["alias"],
            "range": range_list(import_record),
        }
        for import_record in imports
    ]
    return sorted(
        rows,
        key=lambda row: (
            row["file"],
            row["range"],
            row["kind"],
            row["module"] or "",
            row["name"] or "",
            row["alias"] or "",
        ),
    )


def make_import_resolution_rows(
    import_resolutions: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for resolution in import_resolutions:
        target_symbol = (
            None
            if resolution["target_symbol_id"] is None
            else symbol_key(symbol_by_id[resolution["target_symbol_id"]], file_by_id)
        )
        rows.append(
            {
                "key": import_resolution_key(
                    resolution, file_by_id, symbol_by_id, import_by_id
                ),
                "import": import_key(import_by_id[resolution["import_id"]], file_by_id),
                "source_file": file_by_id[resolution["source_file_id"]]["path"],
                "target_file": file_by_id[resolution["target_file_id"]]["path"],
                "target_symbol": target_symbol,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["source_file"],
            row["target_file"],
            row["target_symbol"] or "",
            row["import"],
        ),
    )


def make_export_rows(
    exports: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for export in exports:
        symbol = (
            None
            if export["symbol_id"] is None
            else symbol_key(symbol_by_id[export["symbol_id"]], file_by_id)
        )
        import_record = (
            None
            if export["import_id"] is None
            else import_key(import_by_id[export["import_id"]], file_by_id)
        )
        rows.append(
            {
                "key": export_key(export, file_by_id),
                "file": file_by_id[export["file_id"]]["path"],
                "kind": export["kind"],
                "name": export["name"],
                "local_name": export["local_name"],
                "source_module": export["source_module"],
                "symbol": symbol,
                "import": import_record,
                "range": range_list(export),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["file"],
            row["range"],
            row["kind"],
            row["name"] or "",
            row["local_name"] or "",
            row["source_module"] or "",
        ),
    )


def make_reference_rows(
    references: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for reference in references:
        source_symbol = (
            None
            if reference["source_symbol_id"] is None
            else symbol_key(symbol_by_id[reference["source_symbol_id"]], file_by_id)
        )
        import_record = (
            None
            if reference["import_id"] is None
            else import_key(import_by_id[reference["import_id"]], file_by_id)
        )
        rows.append(
            {
                "key": reference_key(reference, file_by_id, symbol_by_id, import_by_id),
                "source_file": file_by_id[reference["source_file_id"]]["path"],
                "source_symbol": source_symbol,
                "target_symbol": symbol_key(
                    symbol_by_id[reference["target_symbol_id"]], file_by_id
                ),
                "import": import_record,
                "name": reference["name"],
                "range": range_list(reference),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["source_file"],
            row["range"],
            row["name"],
            row["target_symbol"],
            row["source_symbol"] or "",
            row["import"] or "",
        ),
    )


def make_dependency_rows(
    dependencies: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
    reference_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for dependency in dependencies:
        rows.append(
            {
                "source_symbol": symbol_key(
                    symbol_by_id[dependency["source_symbol_id"]], file_by_id
                ),
                "target_symbol": symbol_key(
                    symbol_by_id[dependency["target_symbol_id"]], file_by_id
                ),
                "source_file": file_by_id[dependency["source_file_id"]]["path"],
                "target_file": file_by_id[dependency["target_file_id"]]["path"],
                "reference_count": dependency["reference_count"],
                "references": [
                    reference_key(reference_by_id[reference_id], file_by_id, symbol_by_id, import_by_id)
                    for reference_id in dependency["reference_ids"]
                ],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["source_symbol"],
            row["target_symbol"],
            row["reference_count"],
            row["references"],
        ),
    )


def make_subclass_edge_rows(
    subclass_edges: list[dict[str, Any]],
    file_by_id: dict[int, dict[str, Any]],
    symbol_by_id: dict[int, dict[str, Any]],
    import_by_id: dict[int, dict[str, Any]],
    reference_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for edge in subclass_edges:
        rows.append(
            {
                "key": subclass_edge_key(
                    edge, file_by_id, symbol_by_id, import_by_id, reference_by_id
                ),
                "source_symbol": symbol_key(
                    symbol_by_id[edge["source_symbol_id"]], file_by_id
                ),
                "target_symbol": symbol_key(
                    symbol_by_id[edge["target_symbol_id"]], file_by_id
                ),
                "source_file": file_by_id[edge["source_file_id"]]["path"],
                "target_file": file_by_id[edge["target_file_id"]]["path"],
                "reference": reference_key(
                    reference_by_id[edge["reference_id"]],
                    file_by_id,
                    symbol_by_id,
                    import_by_id,
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["source_symbol"],
            row["target_symbol"],
            row["reference"],
        ),
    )


def validate_integrity(
    *,
    files: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    imports: list[dict[str, Any]],
    import_resolutions: list[dict[str, Any]],
    exports: list[dict[str, Any]],
    references: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    subclass_edges: list[dict[str, Any]],
    selected_file_count: int | None,
) -> dict[str, int]:
    file_ids = {file["id"] for file in files}
    symbol_ids = {symbol["id"] for symbol in symbols}
    import_ids = {import_record["id"] for import_record in imports}
    reference_ids = {reference["id"] for reference in references}

    missing_symbol_file_links = sum(
        int(symbol["file_id"] not in file_ids) for symbol in symbols
    )
    missing_import_file_links = sum(
        int(import_record["file_id"] not in file_ids) for import_record in imports
    )
    missing_export_file_links = sum(
        int(export["file_id"] not in file_ids) for export in exports
    )
    missing_export_symbol_links = sum(
        int(export["symbol_id"] is not None and export["symbol_id"] not in symbol_ids)
        for export in exports
    )
    missing_export_import_links = sum(
        int(export["import_id"] is not None and export["import_id"] not in import_ids)
        for export in exports
    )
    missing_resolution_import_links = sum(
        int(resolution["import_id"] not in import_ids)
        for resolution in import_resolutions
    )
    missing_resolution_source_file_links = sum(
        int(resolution["source_file_id"] not in file_ids)
        for resolution in import_resolutions
    )
    missing_resolution_target_file_links = sum(
        int(resolution["target_file_id"] not in file_ids)
        for resolution in import_resolutions
    )
    missing_resolution_target_symbol_links = sum(
        int(
            resolution["target_symbol_id"] is not None
            and resolution["target_symbol_id"] not in symbol_ids
        )
        for resolution in import_resolutions
    )
    missing_reference_source_file_links = sum(
        int(reference["source_file_id"] not in file_ids) for reference in references
    )
    missing_reference_source_symbol_links = sum(
        int(
            reference["source_symbol_id"] is not None
            and reference["source_symbol_id"] not in symbol_ids
        )
        for reference in references
    )
    missing_reference_target_symbol_links = sum(
        int(reference["target_symbol_id"] not in symbol_ids) for reference in references
    )
    missing_reference_import_links = sum(
        int(reference["import_id"] is not None and reference["import_id"] not in import_ids)
        for reference in references
    )
    missing_dependency_source_symbol_links = sum(
        int(dependency["source_symbol_id"] not in symbol_ids)
        for dependency in dependencies
    )
    missing_dependency_target_symbol_links = sum(
        int(dependency["target_symbol_id"] not in symbol_ids)
        for dependency in dependencies
    )
    missing_dependency_source_file_links = sum(
        int(dependency["source_file_id"] not in file_ids) for dependency in dependencies
    )
    missing_dependency_target_file_links = sum(
        int(dependency["target_file_id"] not in file_ids) for dependency in dependencies
    )
    missing_dependency_reference_links = sum(
        int(reference_id not in reference_ids)
        for dependency in dependencies
        for reference_id in dependency["reference_ids"]
    )
    missing_subclass_edge_source_symbol_links = sum(
        int(edge["source_symbol_id"] not in symbol_ids) for edge in subclass_edges
    )
    missing_subclass_edge_target_symbol_links = sum(
        int(edge["target_symbol_id"] not in symbol_ids) for edge in subclass_edges
    )
    missing_subclass_edge_source_file_links = sum(
        int(edge["source_file_id"] not in file_ids) for edge in subclass_edges
    )
    missing_subclass_edge_target_file_links = sum(
        int(edge["target_file_id"] not in file_ids) for edge in subclass_edges
    )
    missing_subclass_edge_reference_links = sum(
        int(edge["reference_id"] not in reference_ids) for edge in subclass_edges
    )
    reference_by_id = {reference["id"]: reference for reference in references}
    mismatched_subclass_edge_references = sum(
        int(
            edge["reference_id"] in reference_by_id
            and (
                reference_by_id[edge["reference_id"]]["source_symbol_id"]
                != edge["source_symbol_id"]
                or reference_by_id[edge["reference_id"]]["target_symbol_id"]
                != edge["target_symbol_id"]
                or reference_by_id[edge["reference_id"]]["source_file_id"]
                != edge["source_file_id"]
            )
        )
        for edge in subclass_edges
    )

    selected_file_count_delta = (
        0 if selected_file_count is None else len(files) - selected_file_count
    )
    return {
        "missing_symbol_file_links": missing_symbol_file_links,
        "missing_import_file_links": missing_import_file_links,
        "missing_export_file_links": missing_export_file_links,
        "missing_export_symbol_links": missing_export_symbol_links,
        "missing_export_import_links": missing_export_import_links,
        "missing_resolution_import_links": missing_resolution_import_links,
        "missing_resolution_source_file_links": missing_resolution_source_file_links,
        "missing_resolution_target_file_links": missing_resolution_target_file_links,
        "missing_resolution_target_symbol_links": missing_resolution_target_symbol_links,
        "missing_reference_source_file_links": missing_reference_source_file_links,
        "missing_reference_source_symbol_links": missing_reference_source_symbol_links,
        "missing_reference_target_symbol_links": missing_reference_target_symbol_links,
        "missing_reference_import_links": missing_reference_import_links,
        "missing_dependency_source_symbol_links": missing_dependency_source_symbol_links,
        "missing_dependency_target_symbol_links": missing_dependency_target_symbol_links,
        "missing_dependency_source_file_links": missing_dependency_source_file_links,
        "missing_dependency_target_file_links": missing_dependency_target_file_links,
        "missing_dependency_reference_links": missing_dependency_reference_links,
        "missing_subclass_edge_source_symbol_links": missing_subclass_edge_source_symbol_links,
        "missing_subclass_edge_target_symbol_links": missing_subclass_edge_target_symbol_links,
        "missing_subclass_edge_source_file_links": missing_subclass_edge_source_file_links,
        "missing_subclass_edge_target_file_links": missing_subclass_edge_target_file_links,
        "missing_subclass_edge_reference_links": missing_subclass_edge_reference_links,
        "mismatched_subclass_edge_references": mismatched_subclass_edge_references,
        "selected_file_count_delta": selected_file_count_delta,
    }


def assert_integrity(integrity: dict[str, int]) -> None:
    failures = [f"{name}={value}" for name, value in integrity.items() if value != 0]
    if failures:
        msg = "compact TypeScript snapshot integrity check failed: " + ", ".join(failures)
        raise RuntimeError(msg)


def summary_dict(summary: Any) -> dict[str, int]:
    return dict(summary.as_dict())


def make_snapshot(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    repo, actual_commit = prepare_pinned_repo(args)
    extension_path = None
    if not args.skip_build_extension:
        extension_path = build_rust_extension(args.extension_dir, timeout=args.timeout)
    if str(args.extension_dir) not in sys.path:
        sys.path.insert(0, str(args.extension_dir))

    import graph_sitter_py

    start = time.perf_counter()
    if args.raw_rust_walk:
        repo_root = repo
        selected_file_count = None
        index = graph_sitter_py.index_typescript_path(str(repo_root))
    else:
        repo_root, file_paths = discover_typescript_files(repo)
        selected_file_count = len(file_paths)
        index = graph_sitter_py.index_typescript_paths(str(repo_root), file_paths)
    wall = time.perf_counter() - start

    files = json.loads(index.files_json())
    symbols = json.loads(index.symbols_json())
    imports = json.loads(index.imports_json())
    import_resolutions = json.loads(index.import_resolutions_json())
    exports = json.loads(index.exports_json())
    references = json.loads(index.references_json())
    dependencies = json.loads(index.dependencies_json())
    subclass_edges = json.loads(index.subclass_edges_json())

    file_by_id = {file["id"]: file for file in files}
    symbol_by_id = {symbol["id"]: symbol for symbol in symbols}
    import_by_id = {import_record["id"]: import_record for import_record in imports}
    reference_by_id = {reference["id"]: reference for reference in references}

    file_rows = make_file_rows(files)
    symbol_rows = make_symbol_rows(symbols, file_by_id, symbol_by_id)
    import_rows = make_import_rows(imports, file_by_id)
    import_resolution_rows = make_import_resolution_rows(
        import_resolutions, file_by_id, symbol_by_id, import_by_id
    )
    export_rows = make_export_rows(exports, file_by_id, symbol_by_id, import_by_id)
    reference_rows = make_reference_rows(references, file_by_id, symbol_by_id, import_by_id)
    dependency_rows = make_dependency_rows(
        dependencies, file_by_id, symbol_by_id, import_by_id, reference_by_id
    )
    subclass_edge_rows = make_subclass_edge_rows(
        subclass_edges, file_by_id, symbol_by_id, import_by_id, reference_by_id
    )
    integrity = validate_integrity(
        files=files,
        symbols=symbols,
        imports=imports,
        import_resolutions=import_resolutions,
        exports=exports,
        references=references,
        dependencies=dependencies,
        subclass_edges=subclass_edges,
        selected_file_count=selected_file_count,
    )
    assert_integrity(integrity)

    summary = summary_dict(index.summary())
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "metadata": {
            "name": args.name,
            "repo_url": args.repo_url,
            "ref": args.ref,
            "commit": actual_commit,
            "raw_rust_walk": args.raw_rust_walk,
            "selected_file_count": selected_file_count,
        },
        "summary": {
            **summary,
            "exports": index.export_count,
            "subclass_edges": index.subclass_edge_count,
        },
        "graphs": {
            "files": compact_record_set(file_rows, sample_size=args.sample_size),
            "symbols": compact_record_set(symbol_rows, sample_size=args.sample_size),
            "imports": compact_record_set(import_rows, sample_size=args.sample_size),
            "import_resolutions": compact_record_set(
                import_resolution_rows, sample_size=args.sample_size
            ),
            "exports": compact_record_set(export_rows, sample_size=args.sample_size),
            "references": compact_record_set(reference_rows, sample_size=args.sample_size),
            "dependencies": compact_record_set(
                dependency_rows, sample_size=args.sample_size
            ),
            "subclass_edges": compact_record_set(
                subclass_edge_rows, sample_size=args.sample_size
            ),
        },
        "integrity": integrity,
    }
    observation = {
        "checkout": str(repo),
        "repo_root": str(repo_root),
        "extension_path": str(extension_path) if extension_path else None,
        "wall_seconds": round(wall, 6),
        "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
    }
    return snapshot, observation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or verify a deterministic compact Rust syntax snapshot for a pinned TypeScript/JavaScript repository."
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_REPO_NAME,
        help="Stable name for the pinned repository checkout.",
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository URL.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Remote ref or commit to fetch.")
    parser.add_argument(
        "--expected-commit",
        default=DEFAULT_EXPECTED_COMMIT,
        help="Expected resolved commit SHA. Pass an empty string to disable.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Directory for reusable pinned checkouts.",
    )
    parser.add_argument(
        "--extension-dir",
        type=Path,
        default=DEFAULT_EXTENSION_DIR,
        help="Directory for the built PyO3 extension module.",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=DEFAULT_EXPECTED_SNAPSHOT,
        help="Expected compact snapshot JSON path.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write the observed snapshot JSON.")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write the observed snapshot to --expected instead of comparing.",
    )
    parser.add_argument(
        "--reset-checkout",
        action="store_true",
        help="Delete and recreate the cached checkout before running.",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Do not fetch before checkout; useful for offline reruns with FETCH_HEAD present.",
    )
    parser.add_argument(
        "--skip-build-extension",
        action="store_true",
        help="Reuse an existing graph_sitter_py extension in --extension-dir.",
    )
    parser.add_argument(
        "--raw-rust-walk",
        action="store_true",
        help="Use Rust's raw recursive TS/JS walk instead of Python-selected file paths.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Number of sorted sample rows stored for each graph family.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout in seconds for clone/build child commands.",
    )
    parser.add_argument("--json", action="store_true", help="Print the snapshot JSON instead of a human summary.")
    return parser.parse_args()


def print_human(snapshot: dict[str, Any], observation: dict[str, Any], expected: Path) -> None:
    summary = snapshot["summary"]
    print(f"repo: {snapshot['metadata']['name']} {snapshot['metadata']['commit']}")
    print(f"expected: {expected}")
    print(f"checkout: {observation['checkout']}")
    print(f"repo root: {observation['repo_root']}")
    print(f"raw rust walk: {snapshot['metadata']['raw_rust_walk']}")
    print(f"selected files: {snapshot['metadata']['selected_file_count']}")
    print(
        f"rust TS snapshot: wall={observation['wall_seconds']:.3f}s "
        f"max_rss={observation['max_rss_mb']:.1f} MB"
    )
    print(
        "summary: "
        f"files={summary['files']} symbols={summary['symbols']} imports={summary['imports']} "
        f"import_resolutions={summary['import_resolutions']} "
        f"exports={summary['exports']} references={summary['references']} "
        f"dependencies={summary['dependencies']} subclass_edges={summary['subclass_edges']} "
        f"files_with_errors={summary['files_with_errors']}"
    )
    print(
        "hashes: "
        f"files={snapshot['graphs']['files']['sha256']} "
        f"symbols={snapshot['graphs']['symbols']['sha256']} "
        f"imports={snapshot['graphs']['imports']['sha256']} "
        f"import_resolutions={snapshot['graphs']['import_resolutions']['sha256']} "
        f"exports={snapshot['graphs']['exports']['sha256']} "
        f"references={snapshot['graphs']['references']['sha256']} "
        f"dependencies={snapshot['graphs']['dependencies']['sha256']} "
        f"subclass_edges={snapshot['graphs']['subclass_edges']['sha256']}"
    )


def main() -> int:
    args = parse_args()
    if args.expected_commit == "":
        args.expected_commit = None
    snapshot, observation = make_snapshot(args)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.update:
        args.expected.parent.mkdir(parents=True, exist_ok=True)
        args.expected.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        compare_snapshot(snapshot, args.expected)

    if args.json:
        print(
            json.dumps(
                {"observation": observation, "snapshot": snapshot},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print_human(snapshot, observation, args.expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
