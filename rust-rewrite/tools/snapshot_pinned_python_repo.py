#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from benchmark_pinned_python_repo import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_EXPECTED_COMMIT,
    DEFAULT_EXTENSION_DIR,
    DEFAULT_REF,
    DEFAULT_REPO_NAME,
    DEFAULT_REPO_URL,
    build_rust_extension,
    prepare_pinned_repo,
)

DEFAULT_EXPECTED_SNAPSHOT = REPO_ROOT / "rust-rewrite/golden/apache-airflow-2.10.5-rust-compact.json"
SNAPSHOT_SCHEMA_VERSION = 3


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def row_digest(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(stable_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def compact_record_set(rows: list[dict[str, Any]], *, sample_size: int) -> dict[str, Any]:
    return {
        "count": len(rows),
        "sha256": row_digest(rows),
        "samples": rows[:sample_size],
    }


def symbol_key(symbol: Any, file_by_id: dict[int, Any]) -> str:
    file = file_by_id[symbol.file_id]
    return f"{file.path}:{symbol.kind}:{symbol.name}@{symbol.name_range.start_byte}"


def import_key(import_record: Any, file_by_id: dict[int, Any]) -> str:
    file = file_by_id[import_record.file_id]
    module = import_record.module if import_record.module is not None else ""
    name = import_record.name if import_record.name is not None else ""
    alias = import_record.alias if import_record.alias is not None else ""
    return f"{file.path}:{import_record.kind}:{module}:{name}:{alias}@{import_record.range.start_byte}"


def external_module_key(external_module: Any, file_by_id: dict[int, Any], import_by_id: dict[int, Any]) -> str:
    return f"{import_key(import_by_id[external_module.import_id], file_by_id)}:{external_module.name}"


def make_file_rows(codebase: Any) -> list[dict[str, Any]]:
    rows = [
        {
            "path": file.path,
            "module_name": file.module_name,
            "byte_len": file.byte_len,
            "line_count": file.line_count,
            "has_error": file.has_error,
        }
        for file in codebase.rust_files
    ]
    return sorted(rows, key=lambda row: row["path"])


def make_symbol_rows(codebase: Any, file_by_id: dict[int, Any]) -> list[dict[str, Any]]:
    symbol_by_id = {symbol.id: symbol for symbol in codebase.rust_symbols}
    rows = [
        {
            "key": symbol_key(symbol, file_by_id),
            "parent_symbol": None if symbol.parent_symbol_id is None else symbol_key(symbol_by_id[symbol.parent_symbol_id], file_by_id),
            "is_top_level": symbol.is_top_level,
            "file": file_by_id[symbol.file_id].path,
            "kind": symbol.kind,
            "name": symbol.name,
            "range": [symbol.range.start_byte, symbol.range.end_byte],
            "name_range": [symbol.name_range.start_byte, symbol.name_range.end_byte],
        }
        for symbol in codebase.rust_symbols
    ]
    return sorted(rows, key=lambda row: (row["file"], row["kind"], row["name"], row["name_range"]))


def make_import_rows(codebase: Any, file_by_id: dict[int, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "key": import_key(import_record, file_by_id),
            "file": file_by_id[import_record.file_id].path,
            "kind": import_record.kind,
            "module": import_record.module,
            "name": import_record.name,
            "alias": import_record.alias,
            "range": [import_record.range.start_byte, import_record.range.end_byte],
        }
        for import_record in codebase.rust_imports
    ]
    return sorted(rows, key=lambda row: (row["file"], row["range"], row["kind"], row["module"] or "", row["name"] or "", row["alias"] or ""))


def make_import_resolution_rows(
    codebase: Any,
    file_by_id: dict[int, Any],
    symbol_by_id: dict[int, Any],
    import_by_id: dict[int, Any],
) -> list[dict[str, Any]]:
    rows = []
    for resolution in codebase.rust_import_resolutions:
        target_symbol = None if resolution.target_symbol_id is None else symbol_by_id[resolution.target_symbol_id]
        rows.append(
            {
                "import": import_key(import_by_id[resolution.import_id], file_by_id),
                "source_file": file_by_id[resolution.source_file_id].path,
                "target_file": file_by_id[resolution.target_file_id].path,
                "target_symbol": None if target_symbol is None else symbol_key(target_symbol, file_by_id),
            }
        )
    return sorted(rows, key=lambda row: (row["source_file"], row["import"], row["target_file"], row["target_symbol"] or ""))


def make_external_module_rows(
    codebase: Any,
    file_by_id: dict[int, Any],
    import_by_id: dict[int, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "key": external_module_key(external_module, file_by_id, import_by_id),
            "file": file_by_id[external_module.file_id].path,
            "import": import_key(import_by_id[external_module.import_id], file_by_id),
            "module": external_module.module,
            "name": external_module.name,
            "alias": external_module.alias,
            "range": [external_module.range.start_byte, external_module.range.end_byte],
        }
        for external_module in codebase.rust_external_modules
    ]
    return sorted(rows, key=lambda row: (row["file"], row["range"], row["module"] or "", row["name"], row["alias"] or ""))


def make_reference_rows(
    codebase: Any,
    file_by_id: dict[int, Any],
    symbol_by_id: dict[int, Any],
    import_by_id: dict[int, Any],
) -> list[dict[str, Any]]:
    rows = []
    for reference in codebase.rust_references:
        source_symbol = None if reference.source_symbol_id is None else symbol_by_id[reference.source_symbol_id]
        rows.append(
            {
                "source_file": file_by_id[reference.source_file_id].path,
                "source_symbol": None if source_symbol is None else symbol_key(source_symbol, file_by_id),
                "target_symbol": symbol_key(symbol_by_id[reference.target_symbol_id], file_by_id),
                "import": None if reference.import_id is None else import_key(import_by_id[reference.import_id], file_by_id),
                "name": reference.name,
                "range": [reference.range.start_byte, reference.range.end_byte],
            }
        )
    return sorted(rows, key=lambda row: (row["source_file"], row["range"], row["source_symbol"] or "", row["target_symbol"], row["name"]))


def make_external_reference_rows(
    codebase: Any,
    file_by_id: dict[int, Any],
    symbol_by_id: dict[int, Any],
    import_by_id: dict[int, Any],
) -> list[dict[str, Any]]:
    rows = []
    for reference in codebase.rust_external_references:
        source_symbol = None if reference.source_symbol_id is None else symbol_by_id[reference.source_symbol_id]
        rows.append(
            {
                "source_file": file_by_id[reference.source_file_id].path,
                "source_symbol": None if source_symbol is None else symbol_key(source_symbol, file_by_id),
                "import": import_key(import_by_id[reference.import_id], file_by_id),
                "name": reference.name,
                "range": [reference.range.start_byte, reference.range.end_byte],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["source_file"],
            row["range"],
            row["source_symbol"] or "",
            row["import"],
            row["name"],
        ),
    )


def make_dependency_rows(
    codebase: Any,
    file_by_id: dict[int, Any],
    symbol_by_id: dict[int, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "source_file": file_by_id[dependency.source_file_id].path,
            "source_symbol": symbol_key(symbol_by_id[dependency.source_symbol_id], file_by_id),
            "target_file": file_by_id[dependency.target_file_id].path,
            "target_symbol": symbol_key(symbol_by_id[dependency.target_symbol_id], file_by_id),
            "reference_count": dependency.reference_count,
        }
        for dependency in codebase.rust_dependencies
    ]
    return sorted(rows, key=lambda row: (row["source_symbol"], row["target_symbol"], row["reference_count"]))


def validate_integrity(codebase: Any) -> dict[str, int]:
    file_ids = {file.id for file in codebase.rust_files}
    symbol_ids = {symbol.id for symbol in codebase.rust_symbols}
    import_ids = {import_record.id for import_record in codebase.rust_imports}
    reference_by_id = {reference.id: reference for reference in codebase.rust_references}

    missing_external_module_links = 0
    for external_module in codebase.rust_external_modules:
        missing_external_module_links += int(external_module.import_id not in import_ids)
        missing_external_module_links += int(external_module.file_id not in file_ids)

    missing_import_resolution_links = 0
    for resolution in codebase.rust_import_resolutions:
        missing_import_resolution_links += int(resolution.import_id not in import_ids)
        missing_import_resolution_links += int(resolution.source_file_id not in file_ids)
        missing_import_resolution_links += int(resolution.target_file_id not in file_ids)
        if resolution.target_symbol_id is not None:
            missing_import_resolution_links += int(resolution.target_symbol_id not in symbol_ids)

    missing_reference_links = 0
    for reference in codebase.rust_references:
        missing_reference_links += int(reference.source_file_id not in file_ids)
        missing_reference_links += int(reference.target_symbol_id not in symbol_ids)
        if reference.source_symbol_id is not None:
            missing_reference_links += int(reference.source_symbol_id not in symbol_ids)
        if reference.import_id is not None:
            missing_reference_links += int(reference.import_id not in import_ids)

    missing_external_reference_links = 0
    for reference in codebase.rust_external_references:
        missing_external_reference_links += int(reference.source_file_id not in file_ids)
        missing_external_reference_links += int(reference.import_id not in import_ids)
        if reference.source_symbol_id is not None:
            missing_external_reference_links += int(reference.source_symbol_id not in symbol_ids)

    missing_dependency_links = 0
    bad_dependency_reference_counts = 0
    bad_dependency_reference_targets = 0
    for dependency in codebase.rust_dependencies:
        missing_dependency_links += int(dependency.source_file_id not in file_ids)
        missing_dependency_links += int(dependency.target_file_id not in file_ids)
        missing_dependency_links += int(dependency.source_symbol_id not in symbol_ids)
        missing_dependency_links += int(dependency.target_symbol_id not in symbol_ids)
        if dependency.reference_count != len(dependency.reference_ids):
            bad_dependency_reference_counts += 1
        for reference_id in dependency.reference_ids:
            reference = reference_by_id.get(reference_id)
            if reference is None:
                missing_dependency_links += 1
                continue
            if reference.source_symbol_id != dependency.source_symbol_id or reference.target_symbol_id != dependency.target_symbol_id:
                bad_dependency_reference_targets += 1

    return {
        "missing_external_module_links": missing_external_module_links,
        "missing_import_resolution_links": missing_import_resolution_links,
        "missing_reference_links": missing_reference_links,
        "missing_external_reference_links": missing_external_reference_links,
        "missing_dependency_links": missing_dependency_links,
        "bad_dependency_reference_counts": bad_dependency_reference_counts,
        "bad_dependency_reference_targets": bad_dependency_reference_targets,
    }


def assert_integrity(integrity: dict[str, int]) -> None:
    failures = [f"{name}={value}" for name, value in integrity.items() if value != 0]
    if failures:
        msg = "compact graph integrity check failed: " + ", ".join(failures)
        raise RuntimeError(msg)


def make_snapshot(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    repo, actual_commit = prepare_pinned_repo(args)
    extension_path = None
    if not args.skip_build_extension:
        extension_path = build_rust_extension(args.extension_dir, timeout=args.timeout)
    if str(args.extension_dir) not in sys.path:
        sys.path.insert(0, str(args.extension_dir))

    from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
    from graph_sitter.core.codebase import Codebase

    start = time.perf_counter()
    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)
    codebase = Codebase(str(repo), language="python", config=config)
    wall = time.perf_counter() - start

    file_by_id = {file.id: file for file in codebase.rust_files}
    symbol_by_id = {symbol.id: symbol for symbol in codebase.rust_symbols}
    import_by_id = {import_record.id: import_record for import_record in codebase.rust_imports}

    file_rows = make_file_rows(codebase)
    symbol_rows = make_symbol_rows(codebase, file_by_id)
    import_rows = make_import_rows(codebase, file_by_id)
    import_resolution_rows = make_import_resolution_rows(codebase, file_by_id, symbol_by_id, import_by_id)
    external_module_rows = make_external_module_rows(codebase, file_by_id, import_by_id)
    reference_rows = make_reference_rows(codebase, file_by_id, symbol_by_id, import_by_id)
    external_reference_rows = make_external_reference_rows(codebase, file_by_id, symbol_by_id, import_by_id)
    dependency_rows = make_dependency_rows(codebase, file_by_id, symbol_by_id)
    integrity = validate_integrity(codebase)
    assert_integrity(integrity)

    summary = codebase.rust_index_summary
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "metadata": {
            "name": args.name,
            "repo_url": args.repo_url,
            "ref": args.ref,
            "commit": actual_commit,
        },
        "summary": {
            "files": summary.files,
            "symbols": summary.symbols,
            "classes": summary.classes,
            "functions": summary.functions,
            "global_variables": summary.global_variables,
            "imports": summary.imports,
            "import_resolutions": summary.import_resolutions,
            "external_modules": len(codebase.rust_external_modules),
            "references": summary.references,
            "external_references": len(codebase.rust_external_references),
            "dependencies": summary.dependencies,
            "bytes": summary.bytes,
            "lines": summary.lines,
            "files_with_errors": summary.files_with_errors,
        },
        "graphs": {
            "files": compact_record_set(file_rows, sample_size=args.sample_size),
            "symbols": compact_record_set(symbol_rows, sample_size=args.sample_size),
            "imports": compact_record_set(import_rows, sample_size=args.sample_size),
            "import_resolutions": compact_record_set(import_resolution_rows, sample_size=args.sample_size),
            "external_modules": compact_record_set(external_module_rows, sample_size=args.sample_size),
            "references": compact_record_set(reference_rows, sample_size=args.sample_size),
            "external_references": compact_record_set(external_reference_rows, sample_size=args.sample_size),
            "dependencies": compact_record_set(dependency_rows, sample_size=args.sample_size),
        },
        "integrity": integrity,
    }
    observation = {
        "checkout": str(repo),
        "extension_path": str(extension_path) if extension_path else None,
        "wall_seconds": round(wall, 6),
        "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
    }
    return snapshot, observation


def compare_snapshot(actual: dict[str, Any], expected_path: Path) -> None:
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if actual == expected:
        return

    mismatches = []
    for key in ("metadata", "summary", "integrity"):
        if actual.get(key) != expected.get(key):
            mismatches.append(key)
    for graph_name, graph in actual.get("graphs", {}).items():
        expected_graph = expected.get("graphs", {}).get(graph_name)
        if graph != expected_graph:
            mismatches.append(f"graphs.{graph_name}")
    msg = f"snapshot mismatch against {expected_path}: {', '.join(mismatches)}"
    raise AssertionError(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or verify a deterministic compact Rust graph snapshot for a pinned Python repository.")
    parser.add_argument("--name", default=DEFAULT_REPO_NAME, help="Stable name for the pinned repository checkout.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository URL.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Remote ref or commit to fetch.")
    parser.add_argument("--expected-commit", default=DEFAULT_EXPECTED_COMMIT, help="Expected resolved commit SHA. Pass an empty string to disable.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Directory for reusable pinned checkouts.")
    parser.add_argument("--extension-dir", type=Path, default=DEFAULT_EXTENSION_DIR, help="Directory for the built PyO3 extension module.")
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED_SNAPSHOT, help="Expected compact snapshot JSON path.")
    parser.add_argument("--output", type=Path, help="Optional path to write the observed snapshot JSON.")
    parser.add_argument("--update", action="store_true", help="Write the observed snapshot to --expected instead of comparing.")
    parser.add_argument("--reset-checkout", action="store_true", help="Delete and recreate the cached checkout before running.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch before checkout; useful for offline reruns with FETCH_HEAD present.")
    parser.add_argument("--skip-build-extension", action="store_true", help="Reuse an existing graph_sitter_py extension in --extension-dir.")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of sorted sample rows stored for each graph family.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for clone/build child commands.")
    parser.add_argument("--json", action="store_true", help="Print the snapshot JSON instead of a human summary.")
    return parser.parse_args()


def print_human(snapshot: dict[str, Any], observation: dict[str, Any], expected: Path) -> None:
    summary = snapshot["summary"]
    print(f"repo: {snapshot['metadata']['name']} {snapshot['metadata']['commit']}")
    print(f"expected: {expected}")
    print(f"checkout: {observation['checkout']}")
    print(f"rust snapshot: wall={observation['wall_seconds']:.3f}s max_rss={observation['max_rss_mb']:.1f} MB")
    print(
        "summary: "
        f"files={summary['files']} symbols={summary['symbols']} imports={summary['imports']} "
        f"import_resolutions={summary['import_resolutions']} external_modules={summary['external_modules']} "
        f"references={summary['references']} external_references={summary['external_references']} "
        f"dependencies={summary['dependencies']}"
    )
    print(
        "hashes: "
        f"files={snapshot['graphs']['files']['sha256']} "
        f"imports={snapshot['graphs']['imports']['sha256']} "
        f"external_modules={snapshot['graphs']['external_modules']['sha256']} "
        f"references={snapshot['graphs']['references']['sha256']} "
        f"external_references={snapshot['graphs']['external_references']['sha256']} "
        f"dependencies={snapshot['graphs']['dependencies']['sha256']}"
    )


def main() -> int:
    args = parse_args()
    if args.expected_commit == "":
        args.expected_commit = None
    snapshot, observation = make_snapshot(args)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.update:
        args.expected.parent.mkdir(parents=True, exist_ok=True)
        args.expected.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        compare_snapshot(snapshot, args.expected)

    if args.json:
        print(json.dumps({"observation": observation, "snapshot": snapshot}, indent=2, sort_keys=True))
    else:
        print_human(snapshot, observation, args.expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
