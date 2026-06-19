#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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

from benchmark_pinned_typescript_repo import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_EXPECTED_COMMIT,
    DEFAULT_EXTENSION_DIR,
    DEFAULT_REF,
    DEFAULT_REPO_NAME,
    DEFAULT_REPO_URL,
    build_rust_extension,
    prepare_pinned_repo,
    ratio,
)

EXPECTED_SUMMARY = {
    "files": 13688,
    "symbols": 44870,
    "classes": 502,
    "functions": 13497,
    "global_variables": 28741,
    "imports": 28210,
    "import_resolutions": 13462,
    "external_modules": 13525,
    "references": 114463,
    "dependencies": 49287,
    "bytes": 25421217,
    "lines": 634891,
    "files_with_errors": 114,
}

EXPECTED_RECORDS = {
    "rust_files": 13688,
    "rust_symbols": 44870,
    "rust_classes": 502,
    "rust_functions": 13497,
    "rust_global_vars": 28741,
    "rust_imports": 28210,
    "rust_import_resolutions": 13462,
    "rust_external_modules": 13525,
    "rust_exports": 16026,
    "rust_references": 114463,
    "rust_external_references": 25318,
    "rust_dependencies": 49287,
    "rust_subclass_edges": 160,
}

EXPECTED_COMPAT_HANDLES = {
    "files": 13688,
    "symbols": 23980,
    "classes": 502,
    "functions": 13497,
    "global_vars": 7866,
    "interfaces": 516,
    "types": 1570,
    "imports": 28210,
    "external_modules": 13525,
    "exports": 16026,
}

EXPECTED_KNOWN_GLOBAL_LOOKUPS = {
    "app_router_announcer": {
        "filepath": "packages/next/src/client/components/app-router-announcer.tsx",
        "handle": "RustCompactSymbol",
        "kind": "function",
        "name": "AppRouterAnnouncer",
    }
}

EXPECTED_KNOWN_FILE_LOCAL_EXPORT_LOOKUPS = {
    "app_router_announcer_export": {
        "filepath": "packages/next/src/client/components/app-router-announcer.tsx",
        "handle": "RustCompactExport",
        "kind": "named",
        "name": "AppRouterAnnouncer",
    }
}

EXPECTED_KNOWN_IGNORE_CASE_FILE_LOOKUPS = {
    "app_router_announcer": {
        "filepath": "packages/next/src/client/components/app-router-announcer.tsx",
        "handle": "RustCompactFile",
        "name": "app-router-announcer",
    }
}

EXPECTED_TARGETED_CACHE_MATERIALIZATION = {
    "files": False,
    "symbols": False,
    "imports": False,
    "exports": False,
    "references": False,
    "external_references": False,
    "dependencies": False,
    "file_handles": False,
    "symbol_handles": False,
    "import_handles": False,
    "export_handles": False,
    "exports_by_file": False,
}

EXPECTED_LARGE_CACHE_MATERIALIZATION = {
    "files": False,
    "symbols": False,
    "imports": False,
    "exports": False,
    "references": False,
    "external_references": False,
    "dependencies": False,
}

RECORDED_PYTHON_BASELINE = {
    "wall_seconds": 24.959,
    "max_rss_mb": 3100.1,
}


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


def current_rss_bytes() -> int:
    import psutil

    return int(psutil.Process(os.getpid()).memory_info().rss)


def memory_sample(label: str) -> dict[str, float | str]:
    return {
        "label": label,
        "rss_mb": round(bytes_to_mb(current_rss_bytes()), 3),
        "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
    }


def handle_signature(handle: Any) -> dict[str, Any]:
    signature = {
        "handle": type(handle).__name__,
        "name": handle.name,
    }
    record = getattr(handle, "record", None)
    if record is not None and hasattr(record, "kind"):
        signature["kind"] = record.kind
    return signature


def file_signature(file: Any) -> dict[str, Any]:
    return {
        "filepath": file.filepath,
        "handle": type(file).__name__,
        "name": file.name,
    }


def known_global_lookup_report(codebase: Any) -> dict[str, dict[str, Any]]:
    function = codebase.get_function("AppRouterAnnouncer")
    signature = handle_signature(function)
    signature["filepath"] = function.filepath
    return {
        "app_router_announcer": signature,
    }


def known_file_local_export_lookup_report(codebase: Any) -> dict[str, dict[str, Any]]:
    export = codebase.get_file(
        "packages/next/src/client/components/app-router-announcer.tsx"
    ).get_export("AppRouterAnnouncer")
    signature = handle_signature(export)
    signature["filepath"] = export.filepath
    return {
        "app_router_announcer_export": signature,
    }


def known_ignore_case_file_lookup_report(codebase: Any) -> dict[str, dict[str, Any]]:
    return {
        "app_router_announcer": file_signature(
            codebase.get_file(
                "PACKAGES/NEXT/SRC/CLIENT/COMPONENTS/APP-ROUTER-ANNOUNCER.TSX",
                ignore_case=True,
            )
        ),
    }


def large_cache_materialization_report(backend: Any) -> dict[str, bool]:
    return {
        "files": backend._files is not None,
        "symbols": backend._symbols is not None,
        "imports": backend._imports is not None,
        "exports": backend._exports is not None,
        "references": backend._references is not None,
        "external_references": backend._external_references is not None,
        "dependencies": backend._dependencies is not None,
    }


def targeted_cache_materialization_report(backend: Any) -> dict[str, bool]:
    report = large_cache_materialization_report(backend)
    report["file_handles"] = backend._file_handles is not None
    report["symbol_handles"] = backend._symbol_handles is not None
    report["import_handles"] = backend._import_handles is not None
    report["export_handles"] = backend._export_handles is not None
    report["exports_by_file"] = backend._exports_by_file_id is not None
    return report


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    memory_samples = [memory_sample("start")]
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
    codebase = Codebase(str(repo), language="typescript", config=config)
    wall = time.perf_counter() - start
    memory_samples.append(memory_sample("after_codebase_construct"))

    python_graph_blocked = False
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        python_graph_blocked = True
    memory_samples.append(memory_sample("after_python_graph_block_check"))

    backend = codebase.ctx.rust_index
    assert backend is not None
    summary = codebase.rust_index_summary
    summary_counts = {
        "files": summary.files,
        "symbols": summary.symbols,
        "classes": summary.classes,
        "functions": summary.functions,
        "global_variables": summary.global_variables,
        "imports": summary.imports,
        "import_resolutions": summary.import_resolutions,
        "external_modules": summary.external_modules,
        "references": summary.references,
        "dependencies": summary.dependencies,
        "bytes": summary.bytes,
        "lines": summary.lines,
        "files_with_errors": summary.files_with_errors,
    }
    memory_samples.append(memory_sample("after_summary_counts"))
    record_counts = backend.compact_record_counts()
    memory_samples.append(memory_sample("after_record_counts"))
    compat_counts = backend.compact_compat_counts()
    memory_samples.append(memory_sample("after_compat_handles"))
    known_global_lookups = known_global_lookup_report(codebase)
    memory_samples.append(memory_sample("after_known_global_lookups"))
    known_file_local_export_lookups = known_file_local_export_lookup_report(codebase)
    memory_samples.append(memory_sample("after_known_file_local_export_lookups"))
    known_ignore_case_file_lookups = known_ignore_case_file_lookup_report(codebase)
    memory_samples.append(memory_sample("after_known_ignore_case_file_lookups"))
    targeted_cache_materialization = targeted_cache_materialization_report(backend)
    large_cache_materialization = large_cache_materialization_report(backend)

    totals = {
        "wall_seconds": round(wall, 6),
        "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
        "current_rss_mb": memory_samples[-1]["rss_mb"],
    }
    comparison = {
        "recorded_python_wall_seconds": RECORDED_PYTHON_BASELINE["wall_seconds"],
        "recorded_python_max_rss_mb": RECORDED_PYTHON_BASELINE["max_rss_mb"],
        "recorded_python_to_rust_wall_ratio": ratio(
            RECORDED_PYTHON_BASELINE["wall_seconds"], totals["wall_seconds"]
        ),
        "recorded_python_to_rust_rss_ratio": ratio(
            RECORDED_PYTHON_BASELINE["max_rss_mb"], totals["max_rss_mb"]
        ),
    }
    report = {
        "metadata": {
            "name": args.name,
            "repo_url": args.repo_url,
            "ref": args.ref,
            "commit": actual_commit,
            "checkout": str(repo),
            "extension_path": str(extension_path) if extension_path else None,
            "python_graph_blocked": python_graph_blocked,
        },
        "totals": totals,
        "rss_samples": memory_samples,
        "summary": summary_counts,
        "records": record_counts,
        "compat_handles": compat_counts,
        "known_global_lookups": known_global_lookups,
        "known_file_local_export_lookups": known_file_local_export_lookups,
        "known_ignore_case_file_lookups": known_ignore_case_file_lookups,
        "targeted_cache_materialization": targeted_cache_materialization,
        "large_cache_materialization": large_cache_materialization,
        "comparison": comparison,
    }
    validate_report(report, args)
    return report


def compare_counts(name: str, observed: dict[str, int], expected: dict[str, int], failures: list[str]) -> None:
    for key, expected_value in expected.items():
        observed_value = observed.get(key)
        if observed_value != expected_value:
            failures.append(f"{name}.{key}: expected {expected_value}, got {observed_value}")


def validate_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    failures: list[str] = []
    if not report["metadata"]["python_graph_blocked"]:
        failures.append("Python graph was materialized")
    if not args.allow_count_drift:
        compare_counts("summary", report["summary"], EXPECTED_SUMMARY, failures)
        compare_counts("records", report["records"], EXPECTED_RECORDS, failures)
        compare_counts("compat_handles", report["compat_handles"], EXPECTED_COMPAT_HANDLES, failures)
        if report["known_global_lookups"] != EXPECTED_KNOWN_GLOBAL_LOOKUPS:
            failures.append("known global lookup results drifted")
        if report["known_file_local_export_lookups"] != EXPECTED_KNOWN_FILE_LOCAL_EXPORT_LOOKUPS:
            failures.append("known file-local export lookup results drifted")
        if report["known_ignore_case_file_lookups"] != EXPECTED_KNOWN_IGNORE_CASE_FILE_LOOKUPS:
            failures.append("known ignore-case file lookup results drifted")
        if report["targeted_cache_materialization"] != EXPECTED_TARGETED_CACHE_MATERIALIZATION:
            failures.append("targeted lookup caches were materialized during known queries")
        if report["large_cache_materialization"] != EXPECTED_LARGE_CACHE_MATERIALIZATION:
            failures.append("large Rust backend caches were materialized during known queries")

    totals = report["totals"]
    comparison = report["comparison"]
    if totals["wall_seconds"] > args.max_wall_seconds:
        failures.append(
            f"wall time {totals['wall_seconds']}s exceeds allowed {args.max_wall_seconds}s"
        )
    if totals["max_rss_mb"] > args.max_rss_mb:
        failures.append(
            f"max RSS {totals['max_rss_mb']} MB exceeds allowed {args.max_rss_mb} MB"
        )
    wall_ratio = comparison["recorded_python_to_rust_wall_ratio"]
    rss_ratio = comparison["recorded_python_to_rust_rss_ratio"]
    if wall_ratio is None or wall_ratio < args.min_recorded_wall_ratio:
        failures.append(
            f"recorded Python/Rust wall ratio {wall_ratio}x is below {args.min_recorded_wall_ratio}x"
        )
    if rss_ratio is None or rss_ratio < args.min_recorded_rss_ratio:
        failures.append(
            f"recorded Python/Rust RSS ratio {rss_ratio}x is below {args.min_recorded_rss_ratio}x"
        )

    if failures:
        raise RuntimeError("; ".join(failures))


def print_human(report: dict[str, Any]) -> None:
    metadata = report["metadata"]
    totals = report["totals"]
    summary = report["summary"]
    compat = report["compat_handles"]
    comparison = report["comparison"]
    print(f"repo: {metadata['name']} {metadata['commit']}")
    print(f"checkout: {metadata['checkout']}")
    print(f"python graph blocked: {metadata['python_graph_blocked']}")
    print(
        f"rust Codebase: wall={totals['wall_seconds']:.3f}s "
        f"max_rss={totals['max_rss_mb']:.1f} MB current_rss={totals['current_rss_mb']:.1f} MB"
    )
    print(
        "rss samples: "
        + " -> ".join(f"{sample['label']}={sample['rss_mb']:.1f} MB" for sample in report["rss_samples"])
    )
    print(
        "summary: "
        f"files={summary['files']} symbols={summary['symbols']} imports={summary['imports']} "
        f"external_modules={summary['external_modules']} exports={compat['exports']} "
        f"references={summary['references']} dependencies={summary['dependencies']} "
        f"external_references={report['records']['rust_external_references']} "
        f"subclass_edges={report['records']['rust_subclass_edges']}"
    )
    print(
        "compat handles: "
        f"files={compat['files']} symbols={compat['symbols']} interfaces={compat['interfaces']} "
        f"types={compat['types']} imports={compat['imports']} exports={compat['exports']}"
        f" external_modules={compat['external_modules']}"
    )
    print(
        "recorded baseline ratios: "
        f"wall={comparison['recorded_python_to_rust_wall_ratio']}x "
        f"rss={comparison['recorded_python_to_rust_rss_ratio']}x"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check pinned Next.js Rust Codebase construction, compatibility handles, and performance ceilings."
    )
    parser.add_argument("--name", default=DEFAULT_REPO_NAME, help="Stable name for the pinned repository checkout.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository URL.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Remote ref or commit to fetch.")
    parser.add_argument("--expected-commit", default=DEFAULT_EXPECTED_COMMIT, help="Expected resolved commit SHA. Pass an empty string to disable.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Directory for reusable pinned checkouts.")
    parser.add_argument("--extension-dir", type=Path, default=DEFAULT_EXTENSION_DIR, help="Directory for the built PyO3 extension module.")
    parser.add_argument("--reset-checkout", action="store_true", help="Delete and recreate the cached checkout before running.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch before checkout; useful for offline reruns with FETCH_HEAD present.")
    parser.add_argument("--skip-build-extension", action="store_true", help="Reuse an existing graph_sitter_py extension in --extension-dir.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for clone/build/benchmark child commands.")
    parser.add_argument("--allow-count-drift", action="store_true", help="Do not fail if compact record or compatibility-handle counts differ from the pinned expectations.")
    parser.add_argument("--max-wall-seconds", type=float, default=15.0, help="Fail if Rust Codebase construction is slower than this ceiling.")
    parser.add_argument("--max-rss-mb", type=float, default=1000.0, help="Fail if process max RSS exceeds this ceiling.")
    parser.add_argument("--min-recorded-wall-ratio", type=float, default=2.0, help="Fail unless the recorded Python baseline divided by Rust wall time is at least this value.")
    parser.add_argument("--min-recorded-rss-ratio", type=float, default=3.0, help="Fail unless the recorded Python baseline divided by Rust max RSS is at least this value.")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.expected_commit == "":
        args.expected_commit = None
    report = make_report(args)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
