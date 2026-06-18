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

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from measure_python_backend import bytes_to_mb, create_python_fixture  # noqa: E402


@dataclass
class SampledProcess:
    command: list[str]
    wall_seconds: float
    rss_peak_mb: float
    stdout: str
    stderr: str


def sample_process(command: list[str], *, cwd: Path, sample_interval: float) -> SampledProcess:
    import psutil

    start = time.perf_counter()
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ps_process = psutil.Process(process.pid)
    rss_peak = 0
    while process.poll() is None:
        try:
            rss_peak = max(rss_peak, int(ps_process.memory_info().rss))
        except psutil.NoSuchProcess:
            break
        time.sleep(sample_interval)
    stdout, stderr = process.communicate()
    try:
        rss_peak = max(rss_peak, int(ps_process.memory_info().rss))
    except psutil.NoSuchProcess:
        pass
    wall = time.perf_counter() - start
    if process.returncode != 0:
        msg = f"command failed with exit {process.returncode}: {' '.join(command)}\n{stderr}"
        raise RuntimeError(msg)
    return SampledProcess(
        command=command,
        wall_seconds=wall,
        rss_peak_mb=round(bytes_to_mb(rss_peak), 3),
        stdout=stdout,
        stderr=stderr,
    )


def run_json(command: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return parse_json_output(result.stdout)


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end < start:
        msg = f"command did not emit JSON output:\n{output}"
        raise ValueError(msg)
    return json.loads(output[start : end + 1])


def rust_example_path() -> Path:
    exe = "index_python.exe" if os.name == "nt" else "index_python"
    return REPO_ROOT / "target" / "release" / "examples" / exe


def build_rust_example() -> None:
    subprocess.run(
        ["cargo", "build", "--release", "-p", "graph-sitter-engine", "--example", "index_python"],
        cwd=REPO_ROOT,
        check=True,
    )


def run_python_backend(repo_path: Path, *, disable_graph: bool) -> dict[str, Any]:
    command = [
        sys.executable,
        str(TOOLS_DIR / "measure_python_backend.py"),
        str(repo_path),
        "--language",
        "python",
        "--skip-object-counts",
        "--json",
    ]
    if disable_graph:
        command.append("--disable-graph")
    return run_json(command, cwd=REPO_ROOT)


def run_rust_index(repo_path: Path, *, sample_interval: float) -> dict[str, Any]:
    command = [str(rust_example_path()), str(repo_path), "--json"]
    sampled = sample_process(command, cwd=REPO_ROOT, sample_interval=sample_interval)
    report = parse_json_output(sampled.stdout)
    report["process"] = {
        "command": " ".join(command),
        "wall_seconds": round(sampled.wall_seconds, 6),
        "rss_peak_mb": sampled.rss_peak_mb,
    }
    return report


def ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.repo is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="graph-sitter-rust-compare-")
        repo_path = create_python_fixture(Path(temp_dir.name), args.fixture_files, args.fixture_functions)
        generated_fixture = True
    else:
        repo_path = Path(args.repo).expanduser().resolve()
        generated_fixture = False

    try:
        if not args.skip_build:
            build_rust_example()
        python_report = run_python_backend(repo_path, disable_graph=args.python_disable_graph)
        rust_report = run_rust_index(repo_path, sample_interval=args.sample_interval)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    python_totals = python_report["totals"]
    rust_process = rust_report["process"]
    comparison = {
        "python_to_rust_wall_ratio": ratio(python_totals["wall_seconds"], rust_report["wall_seconds"]),
        "python_to_rust_process_wall_ratio": ratio(python_totals["wall_seconds"], rust_process["wall_seconds"]),
        "python_to_rust_peak_rss_ratio": ratio(python_totals["max_rss_mb"], rust_process["rss_peak_mb"]),
        "python_wall_seconds": python_totals["wall_seconds"],
        "rust_index_wall_seconds": round(rust_report["wall_seconds"], 6),
        "rust_process_wall_seconds": rust_process["wall_seconds"],
        "python_max_rss_mb": python_totals["max_rss_mb"],
        "rust_sampled_rss_peak_mb": rust_process["rss_peak_mb"],
    }
    return {
        "metadata": {
            "repo_path": str(repo_path),
            "generated_fixture": generated_fixture,
            "fixture_files": args.fixture_files if generated_fixture else None,
            "fixture_functions": args.fixture_functions if generated_fixture else None,
            "python_disable_graph": args.python_disable_graph,
            "python": sys.version,
            "platform": platform.platform(),
            "sample_interval_seconds": args.sample_interval,
        },
        "comparison": comparison,
        "python_backend": python_report,
        "rust_index": rust_report,
    }


def print_human(report: dict[str, Any]) -> None:
    metadata = report["metadata"]
    comparison = report["comparison"]
    python_graph = report["python_backend"]["graph"]
    rust_summary = report["rust_index"]["summary"]
    print(f"repo: {metadata['repo_path']}")
    print(f"python disable_graph: {metadata['python_disable_graph']}")
    print(
        "python backend: "
        f"wall={comparison['python_wall_seconds']:.3f}s "
        f"max_rss={comparison['python_max_rss_mb']:.1f} MB "
        f"nodes={python_graph['nodes']} edges={python_graph['edges']} file_nodes={python_graph['source_file_nodes_total']}"
    )
    print(
        "rust index: "
        f"wall={comparison['rust_index_wall_seconds']:.3f}s "
        f"process_wall={comparison['rust_process_wall_seconds']:.3f}s "
        f"rss_peak={comparison['rust_sampled_rss_peak_mb']:.1f} MB "
        f"files={rust_summary['files']} symbols={rust_summary['symbols']} "
        f"imports={rust_summary['imports']} import_resolutions={rust_summary['import_resolutions']}"
    )
    print(
        "ratios: "
        f"wall={comparison['python_to_rust_wall_ratio']}x "
        f"process_wall={comparison['python_to_rust_process_wall_ratio']}x "
        f"rss={comparison['python_to_rust_peak_rss_ratio']}x"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare current Python backend parse/index cost with the Rust compact Python indexer.")
    parser.add_argument("repo", nargs="?", help="Path to a git repository. If omitted, a generated Python fixture is used.")
    parser.add_argument("--fixture-files", type=int, default=150, help="Generated fixture module count when repo is omitted.")
    parser.add_argument("--fixture-functions", type=int, default=20, help="Generated helper functions per module when repo is omitted.")
    parser.add_argument("--sample-interval", type=float, default=0.005, help="RSS sampling interval for the Rust process.")
    parser.add_argument("--skip-build", action="store_true", help="Do not build the Rust example before running it.")
    parser.add_argument(
        "--python-full-graph",
        action="store_false",
        dest="python_disable_graph",
        help="Compare against the full Python graph instead of parse/object materialization only.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
    parser.set_defaults(python_disable_graph=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
