from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = REPO_ROOT / "rust-rewrite/tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_rollout_readiness as readiness  # noqa: E402


def cloned(value: Any) -> Any:
    return copy.deepcopy(value)


def graph_report(count: int) -> dict[str, Any]:
    return {
        "count": count,
        "samples": [],
        "sha256": "synthetic",
    }


def snapshot_report(
    *,
    schema_version: int,
    metadata: dict[str, Any],
    summary: dict[str, int],
    graph_names: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "metadata": metadata,
        "summary": summary,
        "graphs": {name: graph_report(summary[name]) for name in graph_names},
        "integrity": {"missing_links": 0},
    }


def airflow_codebase_report() -> dict[str, Any]:
    return {
        "metadata": {**readiness.AIRFLOW_EXPECTED_METADATA, "python_graph_blocked": True},
        "totals": {"wall_seconds": 1.0, "max_rss_mb": 100.0},
        "summary": cloned(readiness.airflow_codebase.EXPECTED_SUMMARY),
        "records": cloned(readiness.airflow_codebase.EXPECTED_RECORDS),
        "compat_handles": cloned(readiness.airflow_codebase.EXPECTED_COMPAT_HANDLES),
        "known_global_lookups": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_GLOBAL_LOOKUPS),
        "known_child_lookups": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_CHILD_LOOKUPS),
        "known_file_local_lookups": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_FILE_LOCAL_LOOKUPS),
        "known_file_local_import_lookups": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_FILE_LOCAL_IMPORT_LOOKUPS),
        "known_file_local_name_resolution": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_FILE_LOCAL_NAME_RESOLUTION),
        "known_module_import_attribute_resolution": (cloned(readiness.airflow_codebase.EXPECTED_KNOWN_MODULE_IMPORT_ATTRIBUTE_RESOLUTION)),
        "known_ignore_case_file_lookups": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_IGNORE_CASE_FILE_LOOKUPS),
        "targeted_cache_materialization": cloned(readiness.airflow_codebase.EXPECTED_TARGETED_CACHE_MATERIALIZATION),
        "known_lookups": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_LOOKUPS),
        "byte_range_cache_materialization": cloned(readiness.airflow_codebase.EXPECTED_BYTE_RANGE_CACHE_MATERIALIZATION),
        "known_dependencies": cloned(readiness.airflow_codebase.EXPECTED_KNOWN_DEPENDENCIES),
        "large_cache_materialization": cloned(readiness.airflow_codebase.EXPECTED_LARGE_CACHE_MATERIALIZATION),
        "comparison": {
            "recorded_python_to_rust_wall_ratio": 10.0,
            "recorded_python_to_rust_rss_ratio": 10.0,
        },
    }


def nextjs_codebase_report() -> dict[str, Any]:
    return {
        "metadata": {**readiness.NEXTJS_EXPECTED_METADATA, "python_graph_blocked": True},
        "totals": {"wall_seconds": 1.0, "max_rss_mb": 100.0},
        "summary": cloned(readiness.nextjs_codebase.EXPECTED_SUMMARY),
        "records": cloned(readiness.nextjs_codebase.EXPECTED_RECORDS),
        "compat_handles": cloned(readiness.nextjs_codebase.EXPECTED_COMPAT_HANDLES),
        "known_global_lookups": cloned(readiness.nextjs_codebase.EXPECTED_KNOWN_GLOBAL_LOOKUPS),
        "known_file_local_export_lookups": (cloned(readiness.nextjs_codebase.EXPECTED_KNOWN_FILE_LOCAL_EXPORT_LOOKUPS)),
        "known_ignore_case_file_lookups": cloned(readiness.nextjs_codebase.EXPECTED_KNOWN_IGNORE_CASE_FILE_LOOKUPS),
        "known_file_local_call_lookups": cloned(readiness.nextjs_codebase.EXPECTED_KNOWN_FILE_LOCAL_CALL_LOOKUPS),
        "targeted_cache_materialization": cloned(readiness.nextjs_codebase.EXPECTED_TARGETED_CACHE_MATERIALIZATION),
        "large_cache_materialization": cloned(readiness.nextjs_codebase.EXPECTED_LARGE_CACHE_MATERIALIZATION),
        "comparison": {
            "recorded_python_to_rust_wall_ratio": 10.0,
            "recorded_python_to_rust_rss_ratio": 10.0,
        },
    }


def codemods_report() -> dict[str, Any]:
    return {
        "suites": [
            {
                "suite": "python",
                "assertions": {"modified_expected_file": True},
                "large_cache_materialization": {"files": False},
                "timings": {
                    "codebase_construct_wall_seconds": 1.0,
                    "codemod_commit_wall_seconds": 0.1,
                },
                "rss_samples": [{"max_rss_mb": 100.0}],
            },
            {
                "suite": "typescript",
                "assertions": {"modified_expected_file": True},
                "large_cache_materialization": {"files": False},
                "timings": {
                    "codebase_construct_wall_seconds": 1.0,
                    "codemod_commit_wall_seconds": 0.1,
                },
                "rss_samples": [{"max_rss_mb": 100.0}],
            },
        ],
    }


def semantic_parity_report() -> dict[str, Any]:
    suite_template = {
        "python": {
            "timings": {"codebase_construct_wall_seconds": 2.0},
            "rss_samples": [{"max_rss_mb": 500.0}],
        },
        "rust": {
            "python_graph_blocked": True,
            "timings": {"codebase_construct_wall_seconds": 1.0},
            "rss_samples": [{"max_rss_mb": 100.0}],
        },
        "comparison": {
            "exact_keys": ["known_files"],
            "expected_known_deltas": {},
            "known_deltas": {},
            "mismatches": [],
            "performance": {
                "wall_ratio": 2.0,
                "rss_ratio": 5.0,
            },
        },
    }
    return {
        "suites": [
            {"suite": "python", **copy.deepcopy(suite_template)},
            {"suite": "typescript", **copy.deepcopy(suite_template)},
        ],
    }


def complete_reports() -> dict[str, dict[str, Any]]:
    return {
        "airflow_snapshot": snapshot_report(
            schema_version=readiness.airflow_snapshot.SNAPSHOT_SCHEMA_VERSION,
            metadata=readiness.AIRFLOW_EXPECTED_METADATA,
            summary=cloned(readiness.AIRFLOW_EXPECTED_SNAPSHOT_SUMMARY),
            graph_names=[
                "files",
                "symbols",
                "imports",
                "import_resolutions",
                "external_modules",
                "references",
                "external_references",
                "dependencies",
            ],
        ),
        "airflow_codebase": airflow_codebase_report(),
        "nextjs_snapshot": snapshot_report(
            schema_version=readiness.nextjs_snapshot.SNAPSHOT_SCHEMA_VERSION,
            metadata={
                **readiness.NEXTJS_EXPECTED_METADATA,
                "raw_rust_walk": False,
                "selected_file_count": readiness.nextjs_codebase.EXPECTED_SUMMARY["files"],
            },
            summary=cloned(readiness.NEXTJS_EXPECTED_SNAPSHOT_SUMMARY),
            graph_names=[
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
        ),
        "nextjs_codebase": nextjs_codebase_report(),
        "codemods": codemods_report(),
        "semantic_parity": semantic_parity_report(),
    }


def write_reports(report_dir: Path, reports: dict[str, dict[str, Any]]) -> None:
    report_dir.mkdir(exist_ok=True)
    for key, filename in readiness.REQUIRED_REPORTS.items():
        (report_dir / filename).write_text(
            json.dumps(reports[key], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def readiness_args(report_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        report_dir=report_dir,
        min_wall_ratio=2.0,
        min_rss_ratio=4.0,
        output=None,
        json=False,
    )


def test_rollout_readiness_accepts_complete_pinned_contract_reports(tmp_path: Path) -> None:
    write_reports(tmp_path, complete_reports())

    report = readiness.make_report(readiness_args(tmp_path))

    assert report["status"] == "passed"
    assert report["codebase"]["airflow"]["wall_ratio"] == 10.0
    assert report["codebase"]["nextjs"]["rss_ratio"] == 10.0
    assert report["semantic_parity"][0]["wall_ratio"] == 2.0
    assert report["semantic_parity"][0]["rss_ratio"] == 5.0


def test_rollout_readiness_uses_nextjs_hosted_ci_wall_floor_by_default(tmp_path: Path) -> None:
    reports = complete_reports()
    reports["nextjs_codebase"] = copy.deepcopy(reports["nextjs_codebase"])
    reports["nextjs_codebase"]["comparison"]["recorded_python_to_rust_wall_ratio"] = 1.7
    write_reports(tmp_path, reports)

    args = argparse.Namespace(
        report_dir=tmp_path,
        min_wall_ratio=None,
        min_airflow_wall_ratio=None,
        min_nextjs_wall_ratio=None,
        min_semantic_wall_ratio=None,
        min_rss_ratio=4.0,
        output=None,
        json=False,
    )

    report = readiness.make_report(args)

    assert report["status"] == "passed"
    assert report["thresholds"]["min_airflow_wall_ratio"] == 2.0
    assert report["thresholds"]["min_nextjs_wall_ratio"] == 1.2
    assert report["thresholds"]["min_semantic_wall_ratio"] == 2.0
    assert report["codebase"]["nextjs"]["wall_ratio"] == 1.7


def test_rollout_readiness_rejects_stale_codebase_counts(tmp_path: Path) -> None:
    reports = complete_reports()
    reports["airflow_codebase"] = copy.deepcopy(reports["airflow_codebase"])
    reports["airflow_codebase"]["summary"]["files"] -= 1
    write_reports(tmp_path, reports)

    with pytest.raises(RuntimeError, match=r"airflow_codebase\.summary: files"):
        readiness.make_report(readiness_args(tmp_path))


def test_rollout_readiness_rejects_slow_semantic_parity(tmp_path: Path) -> None:
    reports = complete_reports()
    reports["semantic_parity"] = copy.deepcopy(reports["semantic_parity"])
    reports["semantic_parity"]["suites"][0]["comparison"]["performance"]["wall_ratio"] = 1.5
    write_reports(tmp_path, reports)

    with pytest.raises(RuntimeError, match=r"semantic_parity\.python: wall ratio 1\.5x"):
        readiness.make_report(readiness_args(tmp_path))


def test_rollout_readiness_rejects_missing_nextjs_call_proof(tmp_path: Path) -> None:
    reports = complete_reports()
    reports["nextjs_codebase"] = copy.deepcopy(reports["nextjs_codebase"])
    reports["nextjs_codebase"].pop("known_file_local_call_lookups")
    write_reports(tmp_path, reports)

    with pytest.raises(RuntimeError, match=r"nextjs_codebase\.known_file_local_call_lookups"):
        readiness.make_report(readiness_args(tmp_path))
