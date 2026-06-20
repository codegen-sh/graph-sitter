#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]

DEFAULT_REPO_NAME = "apache-airflow-2.10.5"
DEFAULT_REPO_URL = "https://github.com/apache/airflow.git"
DEFAULT_REF = "refs/tags/2.10.5"
DEFAULT_EXPECTED_COMMIT = "b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf"
DEFAULT_CACHE_DIR = Path("/tmp/graph-sitter-pinned-repos")
DEFAULT_EXTENSION_DIR = Path("/tmp/graph_sitter_py_pinned_benchmark")


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, timeout=timeout, check=True, capture_output=True, text=True)


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end < start:
        msg = f"command did not emit JSON output:\n{output}"
        raise ValueError(msg)
    return json.loads(output[start : end + 1])


def git(repo: Path, *args: str, timeout: int | None = None) -> str:
    result = run(["git", *args], cwd=repo, timeout=timeout)
    return result.stdout.strip()


def prepare_pinned_repo(args: argparse.Namespace) -> tuple[Path, str]:
    checkout = args.cache_dir / args.name
    if args.reset_checkout and checkout.exists():
        shutil.rmtree(checkout)
    checkout.parent.mkdir(parents=True, exist_ok=True)

    if not (checkout / ".git").exists():
        checkout.mkdir(parents=True, exist_ok=True)
        git(checkout, "init", timeout=args.timeout)
        git(checkout, "remote", "add", "origin", args.repo_url, timeout=args.timeout)
    else:
        existing_url = git(checkout, "remote", "get-url", "origin", timeout=args.timeout)
        if existing_url != args.repo_url:
            git(checkout, "remote", "set-url", "origin", args.repo_url, timeout=args.timeout)

    if not args.skip_fetch:
        git(checkout, "fetch", "--depth=1", "origin", args.ref, timeout=args.timeout)
    git(checkout, "checkout", "--detach", "FETCH_HEAD", timeout=args.timeout)
    actual_commit = git(checkout, "rev-parse", "HEAD", timeout=args.timeout)
    if args.expected_commit and actual_commit != args.expected_commit:
        msg = f"expected {args.expected_commit} for {args.ref}, got {actual_commit}"
        raise RuntimeError(msg)
    return checkout, actual_commit


def build_rust_extension(extension_dir: Path, *, timeout: int | None) -> Path:
    env = os.environ.copy()
    env["PYO3_PYTHON"] = sys.executable
    if sys.platform == "darwin":
        dynamic_lookup_flags = "-C link-arg=-undefined -C link-arg=dynamic_lookup"
        env["RUSTFLAGS"] = f"{env.get('RUSTFLAGS', '')} {dynamic_lookup_flags}".strip()

    subprocess.run(
        ["cargo", "build", "--release", "-p", "graph-sitter-py", "--features", "extension-module"],
        cwd=REPO_ROOT,
        env=env,
        timeout=timeout,
        check=True,
    )

    if sys.platform == "darwin":
        source = REPO_ROOT / "target/release/libgraph_sitter_py.dylib"
    elif os.name == "nt":
        source = REPO_ROOT / "target/release/graph_sitter_py.dll"
    else:
        source = REPO_ROOT / "target/release/libgraph_sitter_py.so"
    if not source.exists():
        msg = f"built extension artifact not found: {source}"
        raise FileNotFoundError(msg)

    extension_dir.mkdir(parents=True, exist_ok=True)
    target = extension_dir / f"graph_sitter_py{sysconfig.get_config_var('EXT_SUFFIX')}"
    shutil.copy2(source, target)
    return target


def run_python_backend(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    command = [
        sys.executable,
        str(TOOLS_DIR / "measure_python_backend.py"),
        str(repo),
        "--language",
        "python",
        "--skip-object-counts",
        "--sample-interval",
        str(args.sample_interval),
        "--json",
    ]
    if args.python_disable_graph:
        command.append("--disable-graph")
    result = run(command, cwd=REPO_ROOT, timeout=args.timeout)
    return parse_json_output(result.stdout)


def run_rust_codebase(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(args.extension_dir) if not pythonpath else f"{args.extension_dir}{os.pathsep}{pythonpath}"
    command = [sys.executable, str(TOOLS_DIR / "measure_codebase_rust_backend.py"), str(repo), "--json"]
    result = run(command, cwd=REPO_ROOT, env=env, timeout=args.timeout)
    return parse_json_output(result.stdout)


def ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    repo, actual_commit = prepare_pinned_repo(args)
    extension_path = None
    if not args.skip_build_extension:
        extension_path = build_rust_extension(args.extension_dir, timeout=args.timeout)

    python_report = run_python_backend(repo, args)
    rust_report = run_rust_codebase(repo, args)

    python_totals = python_report["totals"]
    python_graph = python_report["graph"]
    rust_totals = rust_report["totals"]
    rust_summary = rust_report["summary"]
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
            "file_count_match": python_graph["source_files"] == rust_summary["files"],
            "rust_symbols": rust_summary["symbols"],
            "rust_imports": rust_summary["imports"],
            "rust_import_resolutions": rust_summary["import_resolutions"],
            "rust_external_modules": rust_summary["external_modules"],
            "rust_references": rust_summary["references"],
            "rust_dependencies": rust_summary["dependencies"],
            "python_nodes": python_graph["nodes"],
            "python_edges": python_graph["edges"],
        },
        "python_backend": python_report,
        "rust_codebase": rust_report,
    }
    validate_report(report, args)
    return report


def validate_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    comparison = report["comparison"]
    failures = []
    wall_ratio = comparison["python_to_rust_wall_ratio"]
    rss_ratio = comparison["python_to_rust_rss_ratio"]
    if args.require_file_count_match and not comparison["file_count_match"]:
        failures.append(f"file count mismatch: python={comparison['python_source_files']} rust={comparison['rust_files']}")
    if wall_ratio is None or wall_ratio < args.min_wall_ratio:
        failures.append(f"wall ratio {wall_ratio}x is below required {args.min_wall_ratio}x")
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
    print(
        "python backend: "
        f"wall={comparison['python_wall_seconds']:.3f}s "
        f"max_rss={comparison['python_max_rss_mb']:.1f} MB "
        f"files={comparison['python_source_files']} nodes={comparison['python_nodes']} edges={comparison['python_edges']}"
    )
    print(
        "rust Codebase: "
        f"wall={comparison['rust_wall_seconds']:.3f}s "
        f"max_rss={comparison['rust_max_rss_mb']:.1f} MB "
        f"files={comparison['rust_files']} symbols={comparison['rust_symbols']} imports={comparison['rust_imports']} "
        f"import_resolutions={comparison['rust_import_resolutions']} external_modules={comparison['rust_external_modules']} "
        f"references={comparison['rust_references']} dependencies={comparison['rust_dependencies']}"
    )
    print(f"ratios: wall={comparison['python_to_rust_wall_ratio']}x rss={comparison['python_to_rust_rss_ratio']}x file_count_match={comparison['file_count_match']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark a pinned large Python repository against the compact Rust Codebase backend.")
    parser.add_argument("--name", default=DEFAULT_REPO_NAME, help="Stable name for the pinned repository checkout.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository URL.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Remote ref or commit to fetch.")
    parser.add_argument("--expected-commit", default=DEFAULT_EXPECTED_COMMIT, help="Expected resolved commit SHA. Pass an empty string to disable.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Directory for reusable pinned checkouts.")
    parser.add_argument("--extension-dir", type=Path, default=DEFAULT_EXTENSION_DIR, help="Directory for the built PyO3 extension module.")
    parser.add_argument("--reset-checkout", action="store_true", help="Delete and recreate the cached checkout before running.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch before checkout; useful for offline reruns with FETCH_HEAD present.")
    parser.add_argument("--skip-build-extension", action="store_true", help="Reuse an existing graph_sitter_py extension in --extension-dir.")
    parser.add_argument("--python-full-graph", action="store_false", dest="python_disable_graph", help="Measure the full Python graph instead of parse/object materialization only.")
    parser.add_argument("--sample-interval", type=float, default=0.01, help="RSS sampling interval for the Python backend harness.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for clone/build/benchmark child commands.")
    parser.add_argument("--min-wall-ratio", type=float, default=1.0, help="Fail unless Python wall time divided by Rust wall time is at least this value.")
    parser.add_argument("--min-rss-ratio", type=float, default=1.0, help="Fail unless Python max RSS divided by Rust max RSS is at least this value.")
    parser.add_argument("--allow-file-count-mismatch", action="store_false", dest="require_file_count_match", help="Do not fail if Python and Rust file counts differ.")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
    parser.set_defaults(python_disable_graph=True, require_file_count_match=True)
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
