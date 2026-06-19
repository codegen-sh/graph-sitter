#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = REPO_ROOT / "rust-rewrite/reports"

REQUIRED_REPORTS = {
    "airflow_snapshot": "airflow-rust-compact-snapshot.json",
    "airflow_codebase": "airflow-rust-codebase.json",
    "nextjs_snapshot": "nextjs-rust-compact-snapshot.json",
    "nextjs_codebase": "nextjs-rust-codebase.json",
    "codemods": "pinned-rust-codemods.json",
    "semantic_parity": "pinned-semantic-parity.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        msg = f"missing required report: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def ratio_at_least(value: Any, minimum: float) -> bool:
    return isinstance(value, int | float) and value >= minimum


def assert_no_integrity_failures(name: str, snapshot: dict[str, Any], failures: list[str]) -> None:
    integrity = snapshot.get("integrity")
    if not isinstance(integrity, dict):
        failures.append(f"{name}: missing integrity report")
        return
    drift = {key: value for key, value in integrity.items() if value != 0}
    if drift:
        failures.append(f"{name}: integrity drifted: {drift}")


def assert_nonempty_graphs(name: str, snapshot: dict[str, Any], failures: list[str]) -> None:
    graphs = snapshot.get("graphs")
    if not isinstance(graphs, dict):
        failures.append(f"{name}: missing graph hashes")
        return
    required_graphs = ["files", "symbols", "imports", "import_resolutions", "references", "dependencies"]
    for graph_name in required_graphs:
        graph = graphs.get(graph_name)
        if not isinstance(graph, dict):
            failures.append(f"{name}: missing graph hash for {graph_name}")
            continue
        if graph.get("count", 0) <= 0:
            failures.append(f"{name}: graph {graph_name} is empty")
        if not graph.get("sha256"):
            failures.append(f"{name}: graph {graph_name} is missing sha256")


def assert_codebase_report(
    name: str,
    report: dict[str, Any],
    *,
    min_wall_ratio: float,
    min_rss_ratio: float,
    failures: list[str],
) -> dict[str, Any]:
    metadata = report.get("metadata", {})
    comparison = report.get("comparison", {})
    totals = report.get("totals", {})
    large_caches = report.get("large_cache_materialization", {})

    if not metadata.get("python_graph_blocked"):
        failures.append(f"{name}: Python graph was materialized")
    wall_ratio = comparison.get("recorded_python_to_rust_wall_ratio")
    rss_ratio = comparison.get("recorded_python_to_rust_rss_ratio")
    if not ratio_at_least(wall_ratio, min_wall_ratio):
        failures.append(f"{name}: wall ratio {wall_ratio}x is below {min_wall_ratio}x")
    if not ratio_at_least(rss_ratio, min_rss_ratio):
        failures.append(f"{name}: RSS ratio {rss_ratio}x is below {min_rss_ratio}x")
    materialized = [key for key, value in large_caches.items() if value]
    if materialized:
        failures.append(f"{name}: large Rust caches were materialized: {', '.join(materialized)}")

    return {
        "wall_seconds": totals.get("wall_seconds"),
        "max_rss_mb": totals.get("max_rss_mb"),
        "wall_ratio": wall_ratio,
        "rss_ratio": rss_ratio,
    }


def assert_codemods(report: dict[str, Any], failures: list[str]) -> list[dict[str, Any]]:
    summaries = []
    for suite in report.get("suites", []):
        suite_name = suite.get("suite", "<unknown>")
        failed_assertions = [
            name for name, passed in suite.get("assertions", {}).items() if not passed
        ]
        if failed_assertions:
            failures.append(f"codemods.{suite_name}: failed assertions: {', '.join(failed_assertions)}")
        caches = suite.get("large_cache_materialization", {})
        materialized = [name for name, value in caches.items() if value]
        if materialized:
            failures.append(
                f"codemods.{suite_name}: large Rust caches were materialized: {', '.join(materialized)}"
            )
        timings = suite.get("timings", {})
        max_rss = max((float(sample["max_rss_mb"]) for sample in suite.get("rss_samples", [])), default=None)
        summaries.append(
            {
                "suite": suite_name,
                "construct_wall_seconds": timings.get("codebase_construct_wall_seconds"),
                "codemod_commit_wall_seconds": timings.get("codemod_commit_wall_seconds"),
                "max_rss_mb": max_rss,
            }
        )
    if not summaries:
        failures.append("codemods: no suites were reported")
    return summaries


def assert_semantic_parity(report: dict[str, Any], failures: list[str]) -> list[dict[str, Any]]:
    summaries = []
    for suite in report.get("suites", []):
        suite_name = suite.get("suite", "<unknown>")
        comparison = suite.get("comparison", {})
        mismatches = comparison.get("mismatches", [])
        if mismatches:
            failures.append(f"semantic_parity.{suite_name}: mismatches: {', '.join(mismatches)}")
        if comparison.get("known_deltas") != comparison.get("expected_known_deltas"):
            failures.append(f"semantic_parity.{suite_name}: known deltas do not match expectations")
        rust_report = suite.get("rust", {})
        if not rust_report.get("python_graph_blocked"):
            failures.append(f"semantic_parity.{suite_name}: Rust run materialized the Python graph")

        python_timing = suite.get("python", {}).get("timings", {}).get("codebase_construct_wall_seconds")
        rust_timing = rust_report.get("timings", {}).get("codebase_construct_wall_seconds")
        python_rss = max(
            (float(sample["max_rss_mb"]) for sample in suite.get("python", {}).get("rss_samples", [])),
            default=None,
        )
        rust_rss = max(
            (float(sample["max_rss_mb"]) for sample in rust_report.get("rss_samples", [])),
            default=None,
        )
        summaries.append(
            {
                "suite": suite_name,
                "exact_keys": comparison.get("exact_keys", []),
                "known_delta_count": len(comparison.get("known_deltas", {})),
                "python_wall_seconds": python_timing,
                "rust_wall_seconds": rust_timing,
                "python_max_rss_mb": python_rss,
                "rust_max_rss_mb": rust_rss,
            }
        )
    if not summaries:
        failures.append("semantic_parity: no suites were reported")
    return summaries


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    report_dir = args.report_dir
    reports = {
        key: load_json(report_dir / filename)
        for key, filename in REQUIRED_REPORTS.items()
    }

    failures: list[str] = []
    for name in ("airflow_snapshot", "nextjs_snapshot"):
        assert_no_integrity_failures(name, reports[name], failures)
        assert_nonempty_graphs(name, reports[name], failures)

    codebase_summary = {
        "airflow": assert_codebase_report(
            "airflow_codebase",
            reports["airflow_codebase"],
            min_wall_ratio=args.min_wall_ratio,
            min_rss_ratio=args.min_rss_ratio,
            failures=failures,
        ),
        "nextjs": assert_codebase_report(
            "nextjs_codebase",
            reports["nextjs_codebase"],
            min_wall_ratio=args.min_wall_ratio,
            min_rss_ratio=args.min_rss_ratio,
            failures=failures,
        ),
    }
    codemod_summary = assert_codemods(reports["codemods"], failures)
    semantic_summary = assert_semantic_parity(reports["semantic_parity"], failures)

    readiness = {
        "status": "failed" if failures else "passed",
        "thresholds": {
            "min_wall_ratio": args.min_wall_ratio,
            "min_rss_ratio": args.min_rss_ratio,
        },
        "reports": {key: str(report_dir / filename) for key, filename in REQUIRED_REPORTS.items()},
        "codebase": codebase_summary,
        "codemods": codemod_summary,
        "semantic_parity": semantic_summary,
        "failures": failures,
    }
    if failures:
        msg = "rollout readiness failed: " + "; ".join(failures)
        raise RuntimeError(msg)
    return readiness


def print_human(report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(
        "thresholds: "
        f"wall>={report['thresholds']['min_wall_ratio']}x "
        f"rss>={report['thresholds']['min_rss_ratio']}x"
    )
    for name, summary in report["codebase"].items():
        print(
            f"{name}: wall={summary['wall_seconds']:.3f}s "
            f"rss={summary['max_rss_mb']:.1f} MB "
            f"ratios={summary['wall_ratio']}x/{summary['rss_ratio']}x"
        )
    for summary in report["codemods"]:
        print(
            f"codemod {summary['suite']}: construct={summary['construct_wall_seconds']:.3f}s "
            f"commit={summary['codemod_commit_wall_seconds']:.3f}s "
            f"max_rss={summary['max_rss_mb']:.1f} MB"
        )
    for summary in report["semantic_parity"]:
        print(
            f"semantic {summary['suite']}: exact={len(summary['exact_keys'])} "
            f"known_deltas={summary['known_delta_count']} "
            f"python={summary['python_wall_seconds']:.3f}s/{summary['python_max_rss_mb']:.1f} MB "
            f"rust={summary['rust_wall_seconds']:.3f}s/{summary['rust_max_rss_mb']:.1f} MB"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate rust-rewrite large-repo reports into a single rollout readiness gate."
    )
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--min-wall-ratio",
        type=float,
        default=2.0,
        help="Fail unless recorded Python wall time divided by Rust wall time is at least this value.",
    )
    parser.add_argument(
        "--min-rss-ratio",
        type=float,
        default=4.0,
        help="Fail unless recorded Python max RSS divided by Rust max RSS is at least this value.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write the readiness JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a human summary.")
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
