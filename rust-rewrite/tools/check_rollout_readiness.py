#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import benchmark_pinned_python_repo as airflow_benchmark
import benchmark_pinned_typescript_repo as nextjs_benchmark
import check_pinned_python_codebase as airflow_codebase
import check_pinned_typescript_codebase as nextjs_codebase
import snapshot_pinned_python_repo as airflow_snapshot
import snapshot_pinned_typescript_repo as nextjs_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = REPO_ROOT / "rust-rewrite/reports"
DEFAULT_MIN_AIRFLOW_WALL_RATIO = 2.0
DEFAULT_MIN_NEXTJS_WALL_RATIO = 1.5
DEFAULT_MIN_SEMANTIC_WALL_RATIO = 2.0
DEFAULT_MIN_RSS_RATIO = 4.0

REQUIRED_REPORTS = {
    "airflow_snapshot": "airflow-rust-compact-snapshot.json",
    "airflow_codebase": "airflow-rust-codebase.json",
    "nextjs_snapshot": "nextjs-rust-compact-snapshot.json",
    "nextjs_codebase": "nextjs-rust-codebase.json",
    "codemods": "pinned-rust-codemods.json",
    "semantic_parity": "pinned-semantic-parity.json",
}

AIRFLOW_EXPECTED_SNAPSHOT_SUMMARY = airflow_codebase.EXPECTED_SUMMARY
NEXTJS_EXPECTED_SNAPSHOT_SUMMARY = {
    **nextjs_codebase.EXPECTED_SUMMARY,
    "exports": nextjs_codebase.EXPECTED_RECORDS["rust_exports"],
    "external_references": nextjs_codebase.EXPECTED_RECORDS["rust_external_references"],
    "subclass_edges": nextjs_codebase.EXPECTED_RECORDS["rust_subclass_edges"],
}

AIRFLOW_EXPECTED_METADATA = {
    "name": airflow_benchmark.DEFAULT_REPO_NAME,
    "repo_url": airflow_benchmark.DEFAULT_REPO_URL,
    "ref": airflow_benchmark.DEFAULT_REF,
    "commit": airflow_benchmark.DEFAULT_EXPECTED_COMMIT,
}
NEXTJS_EXPECTED_METADATA = {
    "name": nextjs_benchmark.DEFAULT_REPO_NAME,
    "repo_url": nextjs_benchmark.DEFAULT_REPO_URL,
    "ref": nextjs_benchmark.DEFAULT_REF,
    "commit": nextjs_benchmark.DEFAULT_EXPECTED_COMMIT,
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        msg = f"missing required report: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def ratio_at_least(value: Any, minimum: float) -> bool:
    return isinstance(value, int | float) and value >= minimum


def ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 3)


def resolve_threshold(value: float | None, common: float | None, default: float) -> float:
    if value is not None:
        return value
    if common is not None:
        return common
    return default


def assert_metadata(name: str, metadata: dict[str, Any], expected: dict[str, Any], failures: list[str]) -> None:
    for key, expected_value in expected.items():
        observed_value = metadata.get(key)
        if observed_value != expected_value:
            failures.append(f"{name}: metadata.{key} expected {expected_value!r}, got {observed_value!r}")


def assert_exact_counts(name: str, observed: dict[str, Any], expected: dict[str, int], failures: list[str]) -> None:
    if not isinstance(observed, dict):
        failures.append(f"{name}: missing count mapping")
        return
    for key, expected_value in expected.items():
        observed_value = observed.get(key)
        if observed_value != expected_value:
            failures.append(f"{name}: {key} expected {expected_value}, got {observed_value}")


def assert_exact_mapping(name: str, observed: Any, expected: Any, failures: list[str]) -> None:
    if observed != expected:
        failures.append(f"{name}: drifted")


def assert_cache_contract(name: str, observed: dict[str, Any], expected: dict[str, bool], failures: list[str]) -> None:
    if not isinstance(observed, dict):
        failures.append(f"{name}: missing cache materialization report")
        return
    assert_exact_mapping(name, observed, expected, failures)


def assert_no_integrity_failures(name: str, snapshot: dict[str, Any], failures: list[str]) -> None:
    integrity = snapshot.get("integrity")
    if not isinstance(integrity, dict):
        failures.append(f"{name}: missing integrity report")
        return
    drift = {key: value for key, value in integrity.items() if value != 0}
    if drift:
        failures.append(f"{name}: integrity drifted: {drift}")


def assert_nonempty_graphs(
    name: str,
    snapshot: dict[str, Any],
    failures: list[str],
    *,
    required_graphs: list[str],
) -> None:
    graphs = snapshot.get("graphs")
    if not isinstance(graphs, dict):
        failures.append(f"{name}: missing graph hashes")
        return
    for graph_name in required_graphs:
        graph = graphs.get(graph_name)
        if not isinstance(graph, dict):
            failures.append(f"{name}: missing graph hash for {graph_name}")
            continue
        if graph.get("count", 0) <= 0:
            failures.append(f"{name}: graph {graph_name} is empty")
        if not graph.get("sha256"):
            failures.append(f"{name}: graph {graph_name} is missing sha256")


def assert_snapshot_contract(
    name: str,
    snapshot: dict[str, Any],
    *,
    expected_schema_version: int,
    expected_metadata: dict[str, Any],
    expected_summary: dict[str, int],
    required_graphs: list[str],
    failures: list[str],
) -> None:
    schema_version = snapshot.get("schema_version")
    if schema_version != expected_schema_version:
        failures.append(
            f"{name}: schema_version expected {expected_schema_version}, got {schema_version}"
        )
    assert_metadata(name, snapshot.get("metadata", {}), expected_metadata, failures)
    assert_exact_counts(f"{name}.summary", snapshot.get("summary", {}), expected_summary, failures)
    assert_no_integrity_failures(name, snapshot, failures)
    assert_nonempty_graphs(name, snapshot, failures, required_graphs=required_graphs)
    graphs = snapshot.get("graphs", {})
    if isinstance(graphs, dict):
        for graph_name in required_graphs:
            graph = graphs.get(graph_name, {})
            summary_count = expected_summary.get(graph_name)
            graph_count = graph.get("count") if isinstance(graph, dict) else None
            if summary_count is not None and graph_count != summary_count:
                failures.append(
                    f"{name}: graph {graph_name} count expected {summary_count}, got {graph_count}"
                )


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


def assert_airflow_codebase_contract(report: dict[str, Any], failures: list[str]) -> None:
    assert_metadata("airflow_codebase", report.get("metadata", {}), AIRFLOW_EXPECTED_METADATA, failures)
    assert_exact_counts(
        "airflow_codebase.summary",
        report.get("summary", {}),
        airflow_codebase.EXPECTED_SUMMARY,
        failures,
    )
    assert_exact_counts(
        "airflow_codebase.records",
        report.get("records", {}),
        airflow_codebase.EXPECTED_RECORDS,
        failures,
    )
    assert_exact_counts(
        "airflow_codebase.compat_handles",
        report.get("compat_handles", {}),
        airflow_codebase.EXPECTED_COMPAT_HANDLES,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_global_lookups",
        report.get("known_global_lookups"),
        airflow_codebase.EXPECTED_KNOWN_GLOBAL_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_child_lookups",
        report.get("known_child_lookups"),
        airflow_codebase.EXPECTED_KNOWN_CHILD_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_file_local_lookups",
        report.get("known_file_local_lookups"),
        airflow_codebase.EXPECTED_KNOWN_FILE_LOCAL_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_file_local_import_lookups",
        report.get("known_file_local_import_lookups"),
        airflow_codebase.EXPECTED_KNOWN_FILE_LOCAL_IMPORT_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_file_local_name_resolution",
        report.get("known_file_local_name_resolution"),
        airflow_codebase.EXPECTED_KNOWN_FILE_LOCAL_NAME_RESOLUTION,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_module_import_attribute_resolution",
        report.get("known_module_import_attribute_resolution"),
        airflow_codebase.EXPECTED_KNOWN_MODULE_IMPORT_ATTRIBUTE_RESOLUTION,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_ignore_case_file_lookups",
        report.get("known_ignore_case_file_lookups"),
        airflow_codebase.EXPECTED_KNOWN_IGNORE_CASE_FILE_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_lookups",
        report.get("known_lookups"),
        airflow_codebase.EXPECTED_KNOWN_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "airflow_codebase.known_dependencies",
        report.get("known_dependencies"),
        airflow_codebase.EXPECTED_KNOWN_DEPENDENCIES,
        failures,
    )
    assert_cache_contract(
        "airflow_codebase.targeted_cache_materialization",
        report.get("targeted_cache_materialization", {}),
        airflow_codebase.EXPECTED_TARGETED_CACHE_MATERIALIZATION,
        failures,
    )
    assert_cache_contract(
        "airflow_codebase.byte_range_cache_materialization",
        report.get("byte_range_cache_materialization", {}),
        airflow_codebase.EXPECTED_BYTE_RANGE_CACHE_MATERIALIZATION,
        failures,
    )
    assert_cache_contract(
        "airflow_codebase.large_cache_materialization",
        report.get("large_cache_materialization", {}),
        airflow_codebase.EXPECTED_LARGE_CACHE_MATERIALIZATION,
        failures,
    )


def assert_nextjs_codebase_contract(report: dict[str, Any], failures: list[str]) -> None:
    assert_metadata("nextjs_codebase", report.get("metadata", {}), NEXTJS_EXPECTED_METADATA, failures)
    assert_exact_counts(
        "nextjs_codebase.summary",
        report.get("summary", {}),
        nextjs_codebase.EXPECTED_SUMMARY,
        failures,
    )
    assert_exact_counts(
        "nextjs_codebase.records",
        report.get("records", {}),
        nextjs_codebase.EXPECTED_RECORDS,
        failures,
    )
    assert_exact_counts(
        "nextjs_codebase.compat_handles",
        report.get("compat_handles", {}),
        nextjs_codebase.EXPECTED_COMPAT_HANDLES,
        failures,
    )
    assert_exact_mapping(
        "nextjs_codebase.known_global_lookups",
        report.get("known_global_lookups"),
        nextjs_codebase.EXPECTED_KNOWN_GLOBAL_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "nextjs_codebase.known_file_local_export_lookups",
        report.get("known_file_local_export_lookups"),
        nextjs_codebase.EXPECTED_KNOWN_FILE_LOCAL_EXPORT_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "nextjs_codebase.known_ignore_case_file_lookups",
        report.get("known_ignore_case_file_lookups"),
        nextjs_codebase.EXPECTED_KNOWN_IGNORE_CASE_FILE_LOOKUPS,
        failures,
    )
    assert_exact_mapping(
        "nextjs_codebase.known_file_local_call_lookups",
        report.get("known_file_local_call_lookups"),
        nextjs_codebase.EXPECTED_KNOWN_FILE_LOCAL_CALL_LOOKUPS,
        failures,
    )
    assert_cache_contract(
        "nextjs_codebase.targeted_cache_materialization",
        report.get("targeted_cache_materialization", {}),
        nextjs_codebase.EXPECTED_TARGETED_CACHE_MATERIALIZATION,
        failures,
    )
    assert_cache_contract(
        "nextjs_codebase.large_cache_materialization",
        report.get("large_cache_materialization", {}),
        nextjs_codebase.EXPECTED_LARGE_CACHE_MATERIALIZATION,
        failures,
    )


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


def assert_semantic_parity(
    report: dict[str, Any],
    failures: list[str],
    *,
    min_wall_ratio: float,
    min_rss_ratio: float,
) -> list[dict[str, Any]]:
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
        performance = comparison.get("performance", {})
        wall_ratio = performance.get("wall_ratio") if isinstance(performance, dict) else None
        rss_ratio = performance.get("rss_ratio") if isinstance(performance, dict) else None
        wall_ratio = wall_ratio if wall_ratio is not None else ratio(python_timing, rust_timing)
        rss_ratio = rss_ratio if rss_ratio is not None else ratio(python_rss, rust_rss)
        if not ratio_at_least(wall_ratio, min_wall_ratio):
            failures.append(
                f"semantic_parity.{suite_name}: wall ratio {wall_ratio}x is below {min_wall_ratio}x"
            )
        if not ratio_at_least(rss_ratio, min_rss_ratio):
            failures.append(
                f"semantic_parity.{suite_name}: RSS ratio {rss_ratio}x is below {min_rss_ratio}x"
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
                "wall_ratio": wall_ratio,
                "rss_ratio": rss_ratio,
            }
        )
    if not summaries:
        failures.append("semantic_parity: no suites were reported")
    return summaries


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    report_dir = args.report_dir
    common_wall_ratio = getattr(args, "min_wall_ratio", None)
    min_airflow_wall_ratio = resolve_threshold(
        getattr(args, "min_airflow_wall_ratio", None),
        common_wall_ratio,
        DEFAULT_MIN_AIRFLOW_WALL_RATIO,
    )
    min_nextjs_wall_ratio = resolve_threshold(
        getattr(args, "min_nextjs_wall_ratio", None),
        common_wall_ratio,
        DEFAULT_MIN_NEXTJS_WALL_RATIO,
    )
    min_semantic_wall_ratio = resolve_threshold(
        getattr(args, "min_semantic_wall_ratio", None),
        common_wall_ratio,
        DEFAULT_MIN_SEMANTIC_WALL_RATIO,
    )
    min_rss_ratio = getattr(args, "min_rss_ratio", DEFAULT_MIN_RSS_RATIO)
    reports = {
        key: load_json(report_dir / filename)
        for key, filename in REQUIRED_REPORTS.items()
    }

    failures: list[str] = []
    assert_snapshot_contract(
        "airflow_snapshot",
        reports["airflow_snapshot"],
        expected_schema_version=airflow_snapshot.SNAPSHOT_SCHEMA_VERSION,
        expected_metadata=AIRFLOW_EXPECTED_METADATA,
        expected_summary=AIRFLOW_EXPECTED_SNAPSHOT_SUMMARY,
        required_graphs=[
            "files",
            "symbols",
            "imports",
            "import_resolutions",
            "external_modules",
            "references",
            "external_references",
            "dependencies",
        ],
        failures=failures,
    )
    assert_snapshot_contract(
        "nextjs_snapshot",
        reports["nextjs_snapshot"],
        expected_schema_version=nextjs_snapshot.SNAPSHOT_SCHEMA_VERSION,
        expected_metadata={
            **NEXTJS_EXPECTED_METADATA,
            "raw_rust_walk": False,
            "selected_file_count": nextjs_codebase.EXPECTED_SUMMARY["files"],
        },
        expected_summary=NEXTJS_EXPECTED_SNAPSHOT_SUMMARY,
        required_graphs=[
            "files",
            "symbols",
            "imports",
            "import_resolutions",
            "external_modules",
            "exports",
            "references",
            "external_references",
            "dependencies",
            "subclass_edges",
        ],
        failures=failures,
    )

    codebase_summary = {
        "airflow": assert_codebase_report(
            "airflow_codebase",
            reports["airflow_codebase"],
            min_wall_ratio=min_airflow_wall_ratio,
            min_rss_ratio=min_rss_ratio,
            failures=failures,
        ),
        "nextjs": assert_codebase_report(
            "nextjs_codebase",
            reports["nextjs_codebase"],
            min_wall_ratio=min_nextjs_wall_ratio,
            min_rss_ratio=min_rss_ratio,
            failures=failures,
        ),
    }
    assert_airflow_codebase_contract(reports["airflow_codebase"], failures)
    assert_nextjs_codebase_contract(reports["nextjs_codebase"], failures)
    codemod_summary = assert_codemods(reports["codemods"], failures)
    semantic_summary = assert_semantic_parity(
        reports["semantic_parity"],
        failures,
        min_wall_ratio=min_semantic_wall_ratio,
        min_rss_ratio=min_rss_ratio,
    )

    readiness = {
        "status": "failed" if failures else "passed",
        "thresholds": {
            "min_airflow_wall_ratio": min_airflow_wall_ratio,
            "min_nextjs_wall_ratio": min_nextjs_wall_ratio,
            "min_semantic_wall_ratio": min_semantic_wall_ratio,
            "min_rss_ratio": min_rss_ratio,
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
    thresholds = report["thresholds"]
    print(
        "thresholds: "
        f"airflow_wall>={thresholds['min_airflow_wall_ratio']}x "
        f"nextjs_wall>={thresholds['min_nextjs_wall_ratio']}x "
        f"semantic_wall>={thresholds['min_semantic_wall_ratio']}x "
        f"rss>={thresholds['min_rss_ratio']}x"
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
            f"rust={summary['rust_wall_seconds']:.3f}s/{summary['rust_max_rss_mb']:.1f} MB "
            f"ratios={summary['wall_ratio']}x/{summary['rss_ratio']}x"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate rust-rewrite large-repo reports into a single rollout readiness gate."
    )
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--min-wall-ratio",
        type=float,
        default=None,
        help="Common override for all wall ratio gates.",
    )
    parser.add_argument(
        "--min-airflow-wall-ratio",
        type=float,
        default=None,
        help=f"Airflow Codebase wall-ratio gate. Defaults to {DEFAULT_MIN_AIRFLOW_WALL_RATIO}x.",
    )
    parser.add_argument(
        "--min-nextjs-wall-ratio",
        type=float,
        default=None,
        help=f"Next.js Codebase wall-ratio gate. Defaults to {DEFAULT_MIN_NEXTJS_WALL_RATIO}x.",
    )
    parser.add_argument(
        "--min-semantic-wall-ratio",
        type=float,
        default=None,
        help=f"Semantic parity wall-ratio gate. Defaults to {DEFAULT_MIN_SEMANTIC_WALL_RATIO}x.",
    )
    parser.add_argument(
        "--min-rss-ratio",
        type=float,
        default=DEFAULT_MIN_RSS_RATIO,
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
