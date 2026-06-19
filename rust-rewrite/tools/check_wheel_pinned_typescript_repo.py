#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import benchmark_pinned_typescript_repo as typescript_benchmark
from benchmark_pinned_python_repo import (
    DEFAULT_CACHE_DIR,
    parse_json_output,
    prepare_pinned_repo,
    ratio,
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


@dataclass
class SampledRun:
    command: list[str]
    wall_seconds: float
    rss_peak_mb: float
    stdout: str
    stderr: str

    def as_report(self) -> dict[str, Any]:
        return {
            "command": " ".join(self.command),
            "wall_seconds": round(self.wall_seconds, 6),
            "rss_peak_mb": round(self.rss_peak_mb, 3),
            "stderr": self.stderr.strip(),
        }


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


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


def process_tree_rss(process: Any) -> int:
    import psutil

    rss = 0
    processes = [process]
    try:
        processes.extend(process.children(recursive=True))
    except psutil.Error:
        pass
    for candidate in processes:
        try:
            rss += int(candidate.memory_info().rss)
        except psutil.Error:
            continue
    return rss


def kill_process_tree(process: Any) -> None:
    import psutil

    try:
        children = process.children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try:
            child.kill()
        except psutil.Error:
            continue
    try:
        process.kill()
    except psutil.Error:
        pass


def run_sampled(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    sample_interval: float,
    timeout: int,
) -> SampledRun:
    import psutil

    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ps_process = psutil.Process(process.pid)
    rss_peak = 0
    while process.poll() is None:
        rss_peak = max(rss_peak, process_tree_rss(ps_process))
        if time.perf_counter() - started > timeout:
            kill_process_tree(ps_process)
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        time.sleep(sample_interval)
    stdout, stderr = process.communicate()
    rss_peak = max(rss_peak, process_tree_rss(ps_process))
    wall_seconds = time.perf_counter() - started
    if process.returncode != 0:
        msg = (
            f"command failed with exit {process.returncode}: {' '.join(command)}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
        raise RuntimeError(msg)
    return SampledRun(
        command=command,
        wall_seconds=wall_seconds,
        rss_peak_mb=bytes_to_mb(rss_peak),
        stdout=stdout,
        stderr=stderr,
    )


def graph_sitter_command(wheel: Path, args: argparse.Namespace, *graph_sitter_args: str) -> list[str]:
    return [
        "uvx",
        "--python",
        args.python_version,
        "--from",
        str(wheel),
        "graph-sitter",
        *graph_sitter_args,
    ]


def run_wheel_parse(
    repo: Path,
    wheel: Path,
    args: argparse.Namespace,
    *,
    backend: str,
    env: dict[str, str],
) -> tuple[dict[str, Any], SampledRun]:
    fallback = "error" if backend == "rust" else args.python_backend_fallback
    command = graph_sitter_command(
        wheel,
        args,
        "parse",
        str(repo),
        "--language",
        "typescript",
        "--backend",
        backend,
        "--fallback",
        fallback,
        "--format",
        "json",
    )
    sampled = run_sampled(
        command,
        cwd=REPO_ROOT,
        env=env,
        sample_interval=args.sample_interval,
        timeout=args.timeout,
    )
    return parse_json_output(sampled.stdout), sampled


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


def validate_python_payload(payload: dict[str, Any], expected_summary: dict[str, int]) -> dict[str, Any]:
    failures = []
    if payload.get("backend_requested") != "python":
        failures.append(f"expected backend_requested=python, got {payload.get('backend_requested')}")
    if payload.get("backend") != "python":
        failures.append(f"expected backend=python, got {payload.get('backend')}")
    if payload.get("language") != "typescript":
        failures.append(f"expected language=typescript, got {payload.get('language')}")
    if failures:
        raise RuntimeError("; ".join(failures))
    return {
        "status": "passed",
        "validated_keys": ["backend_requested", "backend", "language"],
        "expected_rust_files": expected_summary["files"],
        "python_files": payload.get("files"),
        "python_to_rust_file_delta": payload.get("files", 0) - expected_summary["files"],
    }


def make_comparison(
    *,
    rust_payload: dict[str, Any],
    rust_sampled: SampledRun,
    python_payload: dict[str, Any],
    python_sampled: SampledRun,
    args: argparse.Namespace,
) -> dict[str, Any]:
    comparison = {
        "python_to_rust_parse_elapsed_ratio": ratio(
            python_payload["elapsed_seconds"],
            rust_payload["elapsed_seconds"],
        ),
        "python_to_rust_outer_wall_ratio": ratio(
            python_sampled.wall_seconds,
            rust_sampled.wall_seconds,
        ),
        "python_to_rust_sampled_rss_ratio": ratio(
            python_sampled.rss_peak_mb,
            rust_sampled.rss_peak_mb,
        ),
        "python_parse_elapsed_seconds": python_payload["elapsed_seconds"],
        "rust_parse_elapsed_seconds": rust_payload["elapsed_seconds"],
        "python_outer_wall_seconds": round(python_sampled.wall_seconds, 6),
        "rust_outer_wall_seconds": round(rust_sampled.wall_seconds, 6),
        "python_sampled_rss_peak_mb": round(python_sampled.rss_peak_mb, 3),
        "rust_sampled_rss_peak_mb": round(rust_sampled.rss_peak_mb, 3),
        "min_parse_elapsed_ratio": args.min_parse_elapsed_ratio,
        "min_sampled_rss_ratio": args.min_sampled_rss_ratio,
    }
    failures = []
    if (
        comparison["python_to_rust_parse_elapsed_ratio"] is None
        or comparison["python_to_rust_parse_elapsed_ratio"] < args.min_parse_elapsed_ratio
    ):
        failures.append(
            "parse elapsed ratio "
            f"{comparison['python_to_rust_parse_elapsed_ratio']}x is below required "
            f"{args.min_parse_elapsed_ratio}x"
        )
    if (
        comparison["python_to_rust_sampled_rss_ratio"] is None
        or comparison["python_to_rust_sampled_rss_ratio"] < args.min_sampled_rss_ratio
    ):
        failures.append(
            "sampled RSS ratio "
            f"{comparison['python_to_rust_sampled_rss_ratio']}x is below required "
            f"{args.min_sampled_rss_ratio}x"
        )
    if failures:
        raise RuntimeError("; ".join(failures))
    comparison["status"] = "passed"
    return comparison


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    repo, actual_commit = prepare_pinned_repo(args)
    wheel = build_wheel(args)
    expected_summary = load_expected_summary(args.expected_snapshot)
    with tempfile.TemporaryDirectory(prefix="graph-sitter-uvx-nextjs-") as scratch:
        env = os.environ.copy()
        uv_cache_dir = Path(scratch) / "uv-cache"
        uv_cache_dir.mkdir()
        env["UV_CACHE_DIR"] = str(uv_cache_dir)

        run(
            graph_sitter_command(wheel, args, "--help"),
            cwd=REPO_ROOT,
            env=env,
            timeout=args.timeout,
        )
        payload, rust_sampled = run_wheel_parse(
            repo,
            wheel,
            args,
            backend="rust",
            env=env,
        )
        python_payload = None
        python_sampled = None
        python_validation = None
        comparison = None
        if args.compare_python_backend:
            python_payload, python_sampled = run_wheel_parse(
                repo,
                wheel,
                args,
                backend="python",
                env=env,
            )
            python_validation = validate_python_payload(python_payload, expected_summary)
            comparison = make_comparison(
                rust_payload=payload,
                rust_sampled=rust_sampled,
                python_payload=python_payload,
                python_sampled=python_sampled,
                args=args,
            )
    validation = validate_payload(
        payload=payload,
        expected_summary=expected_summary,
        expected_commit=args.expected_commit,
        actual_commit=actual_commit,
    )

    report = {
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
            "sample_interval_seconds": args.sample_interval,
        },
        "timings": {
            "parse_elapsed_seconds": payload["elapsed_seconds"],
            "uvx_outer_wall_seconds": round(rust_sampled.wall_seconds, 6),
            "uvx_sampled_rss_peak_mb": round(rust_sampled.rss_peak_mb, 3),
        },
        "parse": payload,
        "rust_process": rust_sampled.as_report(),
        "expected_summary": expected_summary,
        "validation": validation,
    }
    if python_payload is not None and python_sampled is not None:
        report["python_backend"] = {
            "parse": python_payload,
            "process": python_sampled.as_report(),
            "validation": python_validation,
        }
    if comparison is not None:
        report["comparison"] = comparison
    return report


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
        f"outer_wall={timings['uvx_outer_wall_seconds']:.3f}s "
        f"rss_peak={timings['uvx_sampled_rss_peak_mb']:.1f} MB"
    )
    print(
        "counts: "
        f"files={summary['files']} symbols={summary['symbols']} "
        f"imports={summary['imports']} exports={summary['exports']} "
        f"references={summary['references']} dependencies={summary['dependencies']} "
        f"files_with_errors={summary['files_with_errors']}"
    )
    print("validation: matched committed Next.js TypeScript golden summary")
    comparison = report.get("comparison")
    if comparison is not None:
        print(
            "installed-wheel ratios: "
            f"parse_elapsed={comparison['python_to_rust_parse_elapsed_ratio']}x "
            f"outer_wall={comparison['python_to_rust_outer_wall_ratio']}x "
            f"sampled_rss={comparison['python_to_rust_sampled_rss_ratio']}x"
        )


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
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=0.02,
        help="RSS sampling interval for uvx process-tree measurements.",
    )
    parser.add_argument(
        "--compare-python-backend",
        action="store_true",
        help="Also run the installed wheel with --backend python and compare wall/RSS against strict Rust.",
    )
    parser.add_argument(
        "--python-backend-fallback",
        choices=["error", "python"],
        default="error",
        help="Fallback flag passed to the Python backend parse baseline.",
    )
    parser.add_argument(
        "--min-parse-elapsed-ratio",
        type=float,
        default=1.0,
        help="Minimum Python/Rust parse elapsed ratio when --compare-python-backend is enabled.",
    )
    parser.add_argument(
        "--min-sampled-rss-ratio",
        type=float,
        default=1.0,
        help="Minimum Python/Rust sampled process-tree RSS ratio when --compare-python-backend is enabled.",
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
