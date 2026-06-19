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
    "symbols": 23980,
    "classes": 502,
    "functions": 13497,
    "global_variables": 7866,
    "imports": 28210,
    "import_resolutions": 13462,
    "external_modules": 13525,
    "references": 48157,
    "dependencies": 16260,
    "bytes": 25421217,
    "lines": 634891,
    "files_with_errors": 114,
}

EXPECTED_RECORDS = {
    "rust_files": 13688,
    "rust_symbols": 23980,
    "rust_classes": 502,
    "rust_functions": 13497,
    "rust_global_vars": 7866,
    "rust_imports": 28210,
    "rust_import_resolutions": 13462,
    "rust_external_modules": 13525,
    "rust_exports": 16026,
    "rust_references": 48157,
    "rust_external_references": 23282,
    "rust_dependencies": 16260,
    "rust_subclass_edges": 151,
}

EXPECTED_COMPAT_HANDLES = {
    "files": 13688,
    "symbols": 23980,
    "classes": 502,
    "functions": 13497,
    "global_vars": 7866,
    "interfaces": 515,
    "types": 1556,
    "imports": 28210,
    "external_modules": 13525,
    "exports": 16026,
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

    summary = codebase.rust_index_summary
    summary_counts = {
        "files": summary.files,
        "symbols": summary.symbols,
        "classes": summary.classes,
        "functions": summary.functions,
        "global_variables": summary.global_variables,
        "imports": summary.imports,
        "import_resolutions": summary.import_resolutions,
        "external_modules": len(codebase.rust_external_modules),
        "references": summary.references,
        "dependencies": summary.dependencies,
        "bytes": summary.bytes,
        "lines": summary.lines,
        "files_with_errors": summary.files_with_errors,
    }
    memory_samples.append(memory_sample("after_summary_counts"))
    record_counts = {
        "rust_files": len(codebase.rust_files),
        "rust_symbols": len(codebase.rust_symbols),
        "rust_classes": len(codebase.rust_classes),
        "rust_functions": len(codebase.rust_functions),
        "rust_global_vars": len(codebase.rust_global_vars),
        "rust_imports": len(codebase.rust_imports),
        "rust_import_resolutions": len(codebase.rust_import_resolutions),
        "rust_external_modules": len(codebase.rust_external_modules),
        "rust_exports": len(codebase.rust_exports),
        "rust_references": len(codebase.rust_references),
        "rust_external_references": len(codebase.rust_external_references),
        "rust_dependencies": len(codebase.rust_dependencies),
        "rust_subclass_edges": len(codebase.rust_subclass_edges),
    }
    memory_samples.append(memory_sample("after_record_counts"))
    compat_counts = {
        "files": len(codebase.files),
        "symbols": len(codebase.symbols),
        "classes": len(codebase.classes),
        "functions": len(codebase.functions),
        "global_vars": len(codebase.global_vars),
        "interfaces": len(codebase.interfaces),
        "types": len(codebase.types),
        "imports": len(codebase.imports),
        "external_modules": len(codebase.external_modules),
        "exports": len(codebase.exports),
    }
    memory_samples.append(memory_sample("after_compat_handles"))

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
