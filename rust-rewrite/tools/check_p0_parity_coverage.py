#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "rust-rewrite/p0-parity-coverage.json"
ALLOWED_STATUSES = {"parity_covered", "fallback_covered", "open_gap"}
COVERED_STATUSES = {"parity_covered", "fallback_covered"}


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        msg = f"unsupported p0 parity coverage schema version: {manifest.get('schema_version')!r}"
        raise ValueError(msg)
    if not isinstance(manifest.get("pytest_roots"), list) or not manifest["pytest_roots"]:
        msg = "p0 parity coverage manifest must define non-empty pytest_roots"
        raise ValueError(msg)
    if not isinstance(manifest.get("groups"), list) or not manifest["groups"]:
        msg = "p0 parity coverage manifest must define non-empty groups"
        raise ValueError(msg)
    return manifest


def collect_pytest_ids(pytest_roots: list[str]) -> set[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        *pytest_roots,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = f"pytest collection failed with exit code {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        raise RuntimeError(msg)
    return {line.strip() for line in result.stdout.splitlines() if "::test_" in line and line.strip().endswith(tuple("abcdefghijklmnopqrstuvwxyz0123456789_]"))}


def as_string_list(value: object, *, context: str) -> list[str]:
    if not isinstance(value, list) or not value:
        msg = f"{context} must be a non-empty list"
        raise ValueError(msg)
    for item in value:
        if not isinstance(item, str) or not item:
            msg = f"{context} must contain only non-empty strings"
            raise ValueError(msg)
    return value


def evidence_lists(group: dict[str, Any]) -> tuple[list[str], list[str]]:
    evidence = group.get("evidence", {})
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        msg = f"{group.get('name', '<unknown>')}: evidence must be an object"
        raise ValueError(msg)

    pytest_ids = evidence.get("pytest", [])
    tool_paths = evidence.get("tools", [])
    if pytest_ids:
        pytest_ids = as_string_list(pytest_ids, context=f"{group['name']}: evidence.pytest")
    if tool_paths:
        tool_paths = as_string_list(tool_paths, context=f"{group['name']}: evidence.tools")
    return list(pytest_ids), list(tool_paths)


def validate_group(group: dict[str, Any], collected: set[str]) -> tuple[list[str], list[str]]:
    name = group.get("name")
    status = group.get("status")
    if not isinstance(name, str) or not name:
        msg = f"group is missing a name: {group!r}"
        raise ValueError(msg)
    if status not in ALLOWED_STATUSES:
        msg = f"{name}: status must be one of {sorted(ALLOWED_STATUSES)}"
        raise ValueError(msg)

    as_string_list(group.get("api_inventory"), context=f"{name}: api_inventory")
    pytest_ids, tool_paths = evidence_lists(group)

    if status in COVERED_STATUSES and not pytest_ids and not tool_paths:
        msg = f"{name}: {status} groups require pytest or tool evidence"
        raise ValueError(msg)
    if status == "open_gap" and not isinstance(group.get("gap"), str):
        msg = f"{name}: open_gap groups require a gap string"
        raise ValueError(msg)

    missing_tests = sorted(set(pytest_ids) - collected)
    if missing_tests:
        msg = f"{name}: evidence pytest IDs not collected: {', '.join(missing_tests)}"
        raise ValueError(msg)

    missing_tools = sorted(tool for tool in tool_paths if not (REPO_ROOT / tool).exists())
    if missing_tools:
        msg = f"{name}: evidence tool paths not found: {', '.join(missing_tools)}"
        raise ValueError(msg)

    return pytest_ids, tool_paths


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_manifest(args.manifest)
    collected = collect_pytest_ids(manifest["pytest_roots"])

    status_counts: Counter[str] = Counter()
    pytest_evidence: set[str] = set()
    tool_evidence: set[str] = set()
    open_gaps: list[str] = []

    for root in manifest["pytest_roots"]:
        if not (REPO_ROOT / root).exists():
            msg = f"pytest root not found: {root}"
            raise ValueError(msg)

    for group in manifest["groups"]:
        pytest_ids, tool_paths = validate_group(group, collected)
        status = group["status"]
        status_counts[status] += 1
        pytest_evidence.update(pytest_ids)
        tool_evidence.update(tool_paths)
        if status == "open_gap":
            open_gaps.append(group["name"])

    failures: list[str] = []
    if args.require_complete and open_gaps:
        failures.append("open P0 parity gaps remain: " + ", ".join(sorted(open_gaps)))

    report = {
        "status": "failed" if failures else "passed",
        "manifest": str(args.manifest),
        "pytest_roots": manifest["pytest_roots"],
        "group_count": len(manifest["groups"]),
        "status_counts": dict(sorted(status_counts.items())),
        "pytest_evidence_count": len(pytest_evidence),
        "tool_evidence_count": len(tool_evidence),
        "open_gaps": sorted(open_gaps),
        "failures": failures,
    }
    if failures:
        msg = "p0 parity coverage check failed: " + "; ".join(failures)
        raise RuntimeError(msg)
    return report


def print_human(report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"manifest: {report['manifest']}")
    print(f"groups: {report['group_count']}")
    for status, count in report["status_counts"].items():
        print(f"{status}: {count}")
    print(f"pytest evidence: {report['pytest_evidence_count']}")
    print(f"tool evidence: {report['tool_evidence_count']}")
    if report["open_gaps"]:
        print("open gaps:")
        for gap in report["open_gaps"]:
            print(f"  - {gap}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Rust rewrite P0 parity coverage manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail if any P0 group is still marked open_gap.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a human summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = make_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
