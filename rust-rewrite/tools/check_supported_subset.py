#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "rust-rewrite/supported-subset.json"


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        msg = f"unsupported supported-subset schema version: {manifest.get('schema_version')!r}"
        raise ValueError(msg)
    if not isinstance(manifest.get("pytest_roots"), list) or not manifest["pytest_roots"]:
        msg = "supported-subset manifest must define non-empty pytest_roots"
        raise ValueError(msg)
    if not isinstance(manifest.get("capabilities"), list) or not manifest["capabilities"]:
        msg = "supported-subset manifest must define non-empty capabilities"
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


def manifest_test_ids(manifest: dict[str, Any]) -> list[str]:
    test_ids: list[str] = []
    for capability in manifest["capabilities"]:
        name = capability.get("name")
        tests = capability.get("tests")
        if not isinstance(name, str) or not name:
            msg = f"capability is missing a name: {capability!r}"
            raise ValueError(msg)
        if capability.get("status") != "supported_opt_in":
            msg = f"{name}: status must be supported_opt_in"
            raise ValueError(msg)
        if not isinstance(capability.get("scope"), list) or not capability["scope"]:
            msg = f"{name}: scope must be non-empty"
            raise ValueError(msg)
        if not isinstance(tests, list) or not tests:
            msg = f"{name}: tests must be non-empty"
            raise ValueError(msg)
        test_ids.extend(tests)
    return test_ids


def duplicate_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_manifest(args.manifest)
    collected = collect_pytest_ids(manifest["pytest_roots"])
    listed = manifest_test_ids(manifest)
    listed_set = set(listed)

    failures: list[str] = []
    duplicates = duplicate_items(listed)
    if duplicates:
        failures.append("duplicate manifest test ids: " + ", ".join(duplicates))

    missing_from_collection = sorted(listed_set - collected)
    if missing_from_collection:
        failures.append("manifest tests not collected: " + ", ".join(missing_from_collection))

    unlisted_collected = sorted(collected - listed_set)
    if unlisted_collected:
        failures.append("collected supported-subset tests missing from manifest: " + ", ".join(unlisted_collected))

    report = {
        "status": "failed" if failures else "passed",
        "manifest": str(args.manifest),
        "pytest_roots": manifest["pytest_roots"],
        "capability_count": len(manifest["capabilities"]),
        "test_count": len(listed_set),
        "collected_test_count": len(collected),
        "failures": failures,
    }
    if failures:
        msg = "supported subset check failed: " + "; ".join(failures)
        raise RuntimeError(msg)
    return report


def print_human(report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"manifest: {report['manifest']}")
    print(f"capabilities: {report['capability_count']}")
    print(f"tests: {report['test_count']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate that the Rust rewrite supported-subset manifest matches collected fast-lane tests.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
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
