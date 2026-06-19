#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from benchmark_pinned_python_repo import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    build_rust_extension,
    parse_json_output,
    prepare_pinned_repo,
    ratio,
    run,
)

DEFAULT_REPO_NAME = "next.js-v15.0.0"
DEFAULT_REPO_URL = "https://github.com/vercel/next.js.git"
DEFAULT_REF = "refs/tags/v15.0.0"
DEFAULT_EXPECTED_COMMIT = "51bfe3c1863b191f4b039bc230e8ed5c57b0baf3"
DEFAULT_EXTENSION_DIR = Path("/tmp/graph_sitter_py_pinned_typescript_benchmark")


def run_python_backend(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    command = [
        sys.executable,
        str(TOOLS_DIR / "measure_python_backend.py"),
        str(repo),
        "--language",
        "typescript",
        "--skip-object-counts",
        "--sample-interval",
        str(args.sample_interval),
        "--json",
    ]
    if args.python_disable_graph:
        command.append("--disable-graph")
    result = run(command, cwd=REPO_ROOT, timeout=args.timeout)
    return parse_json_output(result.stdout)


def run_rust_typescript_index(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(args.extension_dir)
        if not pythonpath
        else f"{args.extension_dir}{os.pathsep}{pythonpath}"
    )
    command = [
        sys.executable,
        str(TOOLS_DIR / "measure_typescript_rust_index.py"),
        str(repo),
        "--json",
    ]
    if args.raw_rust_walk:
        command.append("--raw-rust-walk")
    result = run(command, cwd=REPO_ROOT, env=env, timeout=args.timeout)
    return parse_json_output(result.stdout)


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    repo, actual_commit = prepare_pinned_repo(args)
    extension_path = None
    if not args.skip_build_extension:
        extension_path = build_rust_extension(args.extension_dir, timeout=args.timeout)

    python_report = run_python_backend(repo, args)
    rust_report = run_rust_typescript_index(repo, args)

    python_totals = python_report["totals"]
    python_graph = python_report["graph"]
    rust_totals = rust_report["totals"]
    rust_summary = rust_report["summary"]
    rust_selected_files = rust_report["metadata"]["selected_file_count"]
    wall_ratio = ratio(python_totals["wall_seconds"], rust_totals["wall_seconds"])
    rss_ratio = ratio(python_totals["max_rss_mb"], rust_totals["max_rss_mb"])

    report = {
        "metadata": {
            "name": args.name,
            "repo_url": args.repo_url,
            "ref": args.ref,
            "commit": actual_commit,
            "checkout": str(repo),
            "python": sys.version,
            "platform": platform.platform(),
            "python_disable_graph": args.python_disable_graph,
            "raw_rust_walk": args.raw_rust_walk,
            "sample_interval_seconds": args.sample_interval,
            "extension_path": str(extension_path) if extension_path else None,
        },
        "comparison": {
            "python_to_rust_wall_ratio": wall_ratio,
            "python_to_rust_rss_ratio": rss_ratio,
            "python_wall_seconds": python_totals["wall_seconds"],
            "rust_wall_seconds": rust_totals["wall_seconds"],
            "python_max_rss_mb": python_totals["max_rss_mb"],
            "rust_max_rss_mb": rust_totals["max_rss_mb"],
            "python_source_files": python_graph["source_files"],
            "rust_files": rust_summary["files"],
            "rust_selected_files": rust_selected_files,
            "selected_file_count_match": rust_selected_files is None
            or rust_selected_files == rust_summary["files"],
            "python_materialized_file_count_match": python_graph["source_files"]
            == rust_summary["files"],
            "python_materialized_file_delta": rust_summary["files"]
            - python_graph["source_files"],
            "rust_symbols": rust_summary["symbols"],
            "rust_classes": rust_summary["classes"],
            "rust_functions": rust_summary["functions"],
            "rust_global_variables": rust_summary["global_variables"],
            "rust_imports": rust_summary["imports"],
            "rust_exports": rust_summary["exports"],
            "rust_files_with_errors": rust_summary["files_with_errors"],
            "python_nodes": python_graph["nodes"],
            "python_edges": python_graph["edges"],
        },
        "python_backend": python_report,
        "rust_typescript_index": rust_report,
    }
    validate_report(report, args)
    return report


def validate_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    comparison = report["comparison"]
    failures = []
    wall_ratio = comparison["python_to_rust_wall_ratio"]
    rss_ratio = comparison["python_to_rust_rss_ratio"]
    if args.require_file_count_match and not comparison["selected_file_count_match"]:
        failures.append(
            "selected file count mismatch: "
            f"selected={comparison['rust_selected_files']} rust={comparison['rust_files']}"
        )
    if wall_ratio is None or wall_ratio < args.min_wall_ratio:
        failures.append(
            f"wall ratio {wall_ratio}x is below required {args.min_wall_ratio}x"
        )
    if rss_ratio is None or rss_ratio < args.min_rss_ratio:
        failures.append(f"RSS ratio {rss_ratio}x is below required {args.min_rss_ratio}x")
    if failures:
        raise RuntimeError("; ".join(failures))


def print_human(report: dict[str, Any]) -> None:
    metadata = report["metadata"]
    comparison = report["comparison"]
    print(f"repo: {metadata['name']} {metadata['commit']}")
    print(f"checkout: {metadata['checkout']}")
    print(f"python disable_graph: {metadata['python_disable_graph']}")
    print(f"raw rust walk: {metadata['raw_rust_walk']}")
    print(
        "python backend: "
        f"wall={comparison['python_wall_seconds']:.3f}s "
        f"max_rss={comparison['python_max_rss_mb']:.1f} MB "
        f"files={comparison['python_source_files']} "
        f"nodes={comparison['python_nodes']} edges={comparison['python_edges']}"
    )
    print(
        "rust TS index: "
        f"wall={comparison['rust_wall_seconds']:.3f}s "
        f"max_rss={comparison['rust_max_rss_mb']:.1f} MB "
        f"files={comparison['rust_files']} symbols={comparison['rust_symbols']} "
        f"imports={comparison['rust_imports']} exports={comparison['rust_exports']} "
        f"files_with_errors={comparison['rust_files_with_errors']}"
    )
    print(
        "ratios: "
        f"wall={comparison['python_to_rust_wall_ratio']}x "
        f"rss={comparison['python_to_rust_rss_ratio']}x "
        f"selected_file_count_match={comparison['selected_file_count_match']} "
        f"python_materialized_delta={comparison['python_materialized_file_delta']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark a pinned large TypeScript/JavaScript repository against the compact Rust TS indexer."
    )
    parser.add_argument("--name", default=DEFAULT_REPO_NAME, help="Stable name for the pinned repository checkout.")
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
        "--python-full-graph",
        action="store_false",
        dest="python_disable_graph",
        help="Measure the full Python graph instead of parse/object materialization only.",
    )
    parser.add_argument(
        "--raw-rust-walk",
        action="store_true",
        help="Use Rust's raw recursive TS/JS walk instead of Python-selected file paths.",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=0.01,
        help="RSS sampling interval for the Python backend harness.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout in seconds for clone/build/benchmark child commands.",
    )
    parser.add_argument(
        "--min-wall-ratio",
        type=float,
        default=1.0,
        help="Fail unless Python wall time divided by Rust wall time is at least this value.",
    )
    parser.add_argument(
        "--min-rss-ratio",
        type=float,
        default=1.0,
        help="Fail unless Python max RSS divided by Rust max RSS is at least this value.",
    )
    parser.add_argument(
        "--allow-file-count-mismatch",
        action="store_false",
        dest="require_file_count_match",
        help="Do not fail if Rust file count differs from the selected TS/JS file list.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument(
        "--json", action="store_true", help="Print JSON report instead of a human summary."
    )
    parser.set_defaults(python_disable_graph=True, require_file_count_match=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.expected_commit == "":
        args.expected_commit = None
    report = make_report(args)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
