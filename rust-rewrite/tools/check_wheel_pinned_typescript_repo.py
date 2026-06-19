#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import benchmark_pinned_typescript_repo as typescript_benchmark
from benchmark_pinned_python_repo import (
    DEFAULT_CACHE_DIR,
    parse_json_output,
    prepare_pinned_repo,
    run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPECTED_SNAPSHOT = (
    REPO_ROOT / "rust-rewrite/golden/next.js-v15.0.0-rust-compact-typescript.json"
)

SUMMARY_KEYS = (
    "files",
    "symbols",
    "classes",
    "functions",
    "global_variables",
    "imports",
    "exports",
    "references",
    "external_references",
    "dependencies",
    "subclass_edges",
    "files_with_errors",
)


def build_wheel(args: argparse.Namespace) -> Path:
    if args.wheel is not None:
        wheel = args.wheel.resolve()
        if not wheel.exists():
            msg = f"wheel does not exist: {wheel}"
            raise FileNotFoundError(msg)
        return wheel

    for wheel in (REPO_ROOT / "dist").glob("graph_sitter-*.whl"):
        wheel.unlink()
    run(["uv", "build", "--wheel"], cwd=REPO_ROOT, timeout=args.timeout)
    wheels = sorted(
        (REPO_ROOT / "dist").glob("graph_sitter-*.whl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not wheels:
        msg = "uv build --wheel did not produce a graph-sitter wheel"
        raise FileNotFoundError(msg)
    return wheels[0].resolve()


def load_expected_summary(path: Path) -> dict[str, int]:
    snapshot = json.loads(path.read_text())
    summary = snapshot["summary"]
    return {key: summary[key] for key in SUMMARY_KEYS}


def run_wheel_parse(repo: Path, wheel: Path, args: argparse.Namespace) -> tuple[dict[str, Any], float]:
    with tempfile.TemporaryDirectory(prefix="graph-sitter-uvx-nextjs-") as scratch:
        env = os.environ.copy()
        uv_cache_dir = Path(scratch) / "uv-cache"
        uv_cache_dir.mkdir()
        env["UV_CACHE_DIR"] = str(uv_cache_dir)

        command = [
            "uvx",
            "--python",
            args.python_version,
            "--from",
            str(wheel),
            "graph-sitter",
            "parse",
            str(repo),
            "--language",
            "typescript",
            "--backend",
            "rust",
            "--fallback",
            "error",
            "--format",
            "json",
        ]
        started = time.perf_counter()
        result = run(command, cwd=REPO_ROOT, env=env, timeout=args.timeout)
        outer_wall_seconds = round(time.perf_counter() - started, 6)
    return parse_json_output(result.stdout), outer_wall_seconds


def validate_payload(
    *,
    payload: dict[str, Any],
    expected_summary: dict[str, int],
    expected_commit: str,
    actual_commit: str,
) -> dict[str, Any]:
    failures: list[str] = []
    if expected_commit and actual_commit != expected_commit:
        failures.append(f"expected commit {expected_commit}, got {actual_commit}")
    if payload.get("backend_requested") != "rust":
        failures.append(f"expected backend_requested=rust, got {payload.get('backend_requested')}")
    if payload.get("backend") != "rust":
        failures.append(f"expected backend=rust, got {payload.get('backend')}")
    if payload.get("language") != "typescript":
        failures.append(f"expected language=typescript, got {payload.get('language')}")
    if payload.get("rust_backend_error") is not None:
        failures.append(f"expected no rust_backend_error, got {payload.get('rust_backend_error')}")

    actual_summary = {key: payload.get(key) for key in SUMMARY_KEYS}
    count_mismatches = {
        key: {"expected": expected, "actual": actual_summary[key]}
        for key, expected in expected_summary.items()
        if actual_summary[key] != expected
    }
    if count_mismatches:
        failures.append(f"summary count mismatches: {count_mismatches}")

    if failures:
        raise RuntimeError("; ".join(failures))

    return {
        "status": "passed",
        "matched_summary_keys": list(SUMMARY_KEYS),
        "actual_summary": actual_summary,
    }


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    repo, actual_commit = prepare_pinned_repo(args)
    wheel = build_wheel(args)
    expected_summary = load_expected_summary(args.expected_snapshot)
    payload, outer_wall_seconds = run_wheel_parse(repo, wheel, args)
    validation = validate_payload(
        payload=payload,
        expected_summary=expected_summary,
        expected_commit=args.expected_commit,
        actual_commit=actual_commit,
    )

    return {
        "metadata": {
            "name": args.name,
            "repo_url": args.repo_url,
            "ref": args.ref,
            "commit": actual_commit,
            "checkout": str(repo),
            "wheel": str(wheel),
            "expected_snapshot": str(args.expected_snapshot),
            "uvx_python_version": args.python_version,
            "python": sys.version,
            "platform": platform.platform(),
        },
        "timings": {
            "parse_elapsed_seconds": payload["elapsed_seconds"],
            "uvx_outer_wall_seconds": outer_wall_seconds,
        },
        "parse": payload,
        "expected_summary": expected_summary,
        "validation": validation,
    }


def print_human(report: dict[str, Any]) -> None:
    metadata = report["metadata"]
    timings = report["timings"]
    summary = report["validation"]["actual_summary"]

    print(f"repo: {metadata['name']} {metadata['commit']}")
    print(f"checkout: {metadata['checkout']}")
    print(f"wheel: {metadata['wheel']}")
    print(
        "uvx parse: "
        f"elapsed={timings['parse_elapsed_seconds']:.3f}s "
        f"outer_wall={timings['uvx_outer_wall_seconds']:.3f}s"
    )
    print(
        "counts: "
        f"files={summary['files']} symbols={summary['symbols']} "
        f"imports={summary['imports']} exports={summary['exports']} "
        f"references={summary['references']} dependencies={summary['dependencies']} "
        f"files_with_errors={summary['files_with_errors']}"
    )
    print("validation: matched committed Next.js TypeScript golden summary")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build or reuse a graph-sitter wheel, run it through uvx against "
            "pinned Next.js, and compare strict Rust parse counts with the "
            "committed TypeScript golden snapshot."
        )
    )
    parser.add_argument("--name", default=typescript_benchmark.DEFAULT_REPO_NAME)
    parser.add_argument("--repo-url", default=typescript_benchmark.DEFAULT_REPO_URL)
    parser.add_argument("--ref", default=typescript_benchmark.DEFAULT_REF)
    parser.add_argument(
        "--expected-commit",
        default=typescript_benchmark.DEFAULT_EXPECTED_COMMIT,
        help="Expected resolved commit SHA. Pass an empty string to disable.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Directory for reusable pinned checkouts.",
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
        "--timeout",
        type=int,
        default=900,
        help="Timeout in seconds for clone/build/uvx child commands.",
    )
    parser.add_argument(
        "--python-version",
        default=os.environ.get("PYTHON_VERSION", "3.13"),
        help="Python version passed to uvx.",
    )
    parser.add_argument(
        "--wheel",
        type=Path,
        help="Existing wheel to test. If omitted, the script builds one with uv build --wheel.",
    )
    parser.add_argument(
        "--expected-snapshot",
        type=Path,
        default=DEFAULT_EXPECTED_SNAPSHOT,
        help="Committed compact TypeScript golden snapshot to compare summary counts against.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = make_report(args)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
