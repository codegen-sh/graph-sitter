#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

import benchmark_pinned_python_repo as python_benchmark
from benchmark_pinned_python_repo import DEFAULT_CACHE_DIR, parse_json_output, ratio, run
from check_wheel_pinned_typescript_repo import (
    SampledRun,
    build_wheel,
    git,
    git_status,
    graph_sitter_command,
    run_sampled,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPECTED_SNAPSHOT = (
    REPO_ROOT / "rust-rewrite/golden/apache-airflow-2.10.5-rust-compact.json"
)

SUMMARY_KEYS = (
    "files",
    "symbols",
    "classes",
    "functions",
    "global_variables",
    "imports",
    "references",
    "external_references",
    "dependencies",
    "files_with_errors",
)

PYTHON_TARGET_FILE = "airflow/__init__.py"
PYTHON_IMPORTED_LINE = "from typing import Any"
PYTHON_RENAMED_FUNCTION = "__getattr_wheel_proof__"


def load_expected_summary(path: Path) -> dict[str, int]:
    snapshot = json.loads(path.read_text())
    summary = snapshot["summary"]
    return {key: summary[key] for key in SUMMARY_KEYS}


def clone_mutable_checkout(cache_repo: Path, commit: str, *, destination: Path, repo_url: str, timeout: int) -> Path:
    checkout = destination / "airflow-transform-repo"
    git(["clone", "--shared", "--no-checkout", str(cache_repo), str(checkout)], cwd=REPO_ROOT, timeout=timeout)
    git(["remote", "set-url", "origin", repo_url], cwd=checkout, timeout=timeout)
    git(["checkout", "--detach", commit], cwd=checkout, timeout=timeout)
    return checkout


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
        "python",
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


def write_airflow_transform(path: Path, *, renamed_function: str) -> None:
    path.write_text(
        f"""def rename(codebase):
    target_file = codebase.get_file({PYTHON_TARGET_FILE!r})
    target_file.add_import({PYTHON_IMPORTED_LINE!r})
    target_file.get_function("__getattr__").rename({renamed_function!r})
    codebase.commit()
""",
        encoding="utf-8",
    )


def run_wheel_transform(
    repo: Path,
    transform: Path,
    wheel: Path,
    args: argparse.Namespace,
    *,
    env: dict[str, str],
) -> SampledRun:
    command = graph_sitter_command(
        wheel,
        args,
        "transform",
        f"{transform}:rename",
        str(repo),
        "--language",
        "python",
        "--backend",
        "rust",
        "--fallback",
        "error",
        "--write",
    )
    return run_sampled(
        command,
        cwd=REPO_ROOT,
        env=env,
        sample_interval=args.sample_interval,
        timeout=args.timeout,
    )


def validate_rust_payload(
    *,
    payload: dict[str, Any],
    expected_summary: dict[str, int],
    expected_commit: str,
    actual_commit: str,
) -> dict[str, Any]:
    failures = []
    if expected_commit and actual_commit != expected_commit:
        failures.append(f"expected commit {expected_commit}, got {actual_commit}")
    if payload.get("backend_requested") != "rust":
        failures.append(f"expected backend_requested=rust, got {payload.get('backend_requested')}")
    if payload.get("backend") != "rust":
        failures.append(f"expected backend=rust, got {payload.get('backend')}")
    if payload.get("language") != "python":
        failures.append(f"expected language=python, got {payload.get('language')}")
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
    if payload.get("exports") != 0:
        failures.append(f"expected exports=0, got {payload.get('exports')}")
    if payload.get("subclass_edges") != 0:
        failures.append(f"expected subclass_edges=0, got {payload.get('subclass_edges')}")
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
    if payload.get("language") != "python":
        failures.append(f"expected language=python, got {payload.get('language')}")
    if failures:
        raise RuntimeError("; ".join(failures))
    return {
        "status": "passed",
        "validated_keys": ["backend_requested", "backend", "language"],
        "expected_rust_files": expected_summary["files"],
        "python_files": payload.get("files"),
        "python_to_rust_file_delta": payload.get("files", 0) - expected_summary["files"],
    }


def validate_transform(checkout: Path, sampled: SampledRun, args: argparse.Namespace) -> dict[str, Any]:
    target_content = (checkout / PYTHON_TARGET_FILE).read_text(encoding="utf-8")
    status = git_status(checkout, timeout=args.timeout)
    modified_paths = {line[2:].lstrip() for line in status if line[:2].strip() == "M"}
    assertions = {
        "added_import": PYTHON_IMPORTED_LINE in target_content,
        "renamed_declaration": f"def {args.transform_new_name}(name: str):" in target_content,
        "removed_original_declaration": "def __getattr__(name: str):" not in target_content,
        "only_target_file_modified": modified_paths == {PYTHON_TARGET_FILE},
        "reported_applied_changes": "Changes have been applied" in sampled.stdout,
    }
    failed = [name for name, passed in assertions.items() if not passed]
    if failed:
        msg = (
            f"installed-wheel Airflow transform assertions failed: {', '.join(failed)}; "
            f"git_status={status!r}"
        )
        raise RuntimeError(msg)
    return {
        "status": "passed",
        "target_file": PYTHON_TARGET_FILE,
        "git_status": status,
        "modified_paths": sorted(modified_paths),
        "assertions": assertions,
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
    repo, actual_commit = python_benchmark.prepare_pinned_repo(args)
    wheel = build_wheel(args)
    expected_summary = load_expected_summary(args.expected_snapshot)

    with tempfile.TemporaryDirectory(prefix="graph-sitter-uvx-airflow-") as scratch:
        env = os.environ.copy()
        uv_cache_dir = Path(scratch) / "uv-cache"
        uv_cache_dir.mkdir()
        env["UV_CACHE_DIR"] = str(uv_cache_dir)

        run(graph_sitter_command(wheel, args, "--help"), cwd=REPO_ROOT, env=env, timeout=args.timeout)
        payload, rust_sampled = run_wheel_parse(repo, wheel, args, backend="rust", env=env)
        python_payload = None
        python_sampled = None
        python_validation = None
        comparison = None
        transform_report = None
        if args.compare_python_backend:
            python_payload, python_sampled = run_wheel_parse(repo, wheel, args, backend="python", env=env)
            python_validation = validate_python_payload(python_payload, expected_summary)
            comparison = make_comparison(
                rust_payload=payload,
                rust_sampled=rust_sampled,
                python_payload=python_payload,
                python_sampled=python_sampled,
                args=args,
            )
        if args.run_transform_proof:
            mutable_checkout = clone_mutable_checkout(
                repo,
                actual_commit,
                destination=Path(scratch),
                repo_url=args.repo_url,
                timeout=args.timeout,
            )
            transform = Path(scratch) / "rename_airflow.py"
            write_airflow_transform(transform, renamed_function=args.transform_new_name)
            transform_sampled = run_wheel_transform(mutable_checkout, transform, wheel, args, env=env)
            transform_validation = validate_transform(mutable_checkout, transform_sampled, args)
            transform_report = {
                "process": transform_sampled.as_report(),
                "renamed_function": args.transform_new_name,
                "validation": transform_validation,
            }

    validation = validate_rust_payload(
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
    if transform_report is not None:
        report["transform"] = transform_report
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
        f"imports={summary['imports']} references={summary['references']} "
        f"dependencies={summary['dependencies']} files_with_errors={summary['files_with_errors']}"
    )
    print("validation: matched committed Airflow Python golden summary")
    comparison = report.get("comparison")
    if comparison is not None:
        print(
            "installed-wheel ratios: "
            f"parse_elapsed={comparison['python_to_rust_parse_elapsed_ratio']}x "
            f"outer_wall={comparison['python_to_rust_outer_wall_ratio']}x "
            f"sampled_rss={comparison['python_to_rust_sampled_rss_ratio']}x"
        )
    transform = report.get("transform")
    if transform is not None:
        process = transform["process"]
        validation = transform["validation"]
        print(
            "uvx transform: "
            f"wall={process['wall_seconds']:.3f}s "
            f"rss_peak={process['rss_peak_mb']:.1f} MB "
            f"modified={', '.join(validation['git_status'])}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build or reuse a graph-sitter wheel, run it through uvx against "
            "pinned Airflow, and compare strict Rust parse counts with the "
            "committed Python golden snapshot."
        )
    )
    parser.add_argument("--name", default=python_benchmark.DEFAULT_REPO_NAME)
    parser.add_argument("--repo-url", default=python_benchmark.DEFAULT_REPO_URL)
    parser.add_argument("--ref", default=python_benchmark.DEFAULT_REF)
    parser.add_argument("--expected-commit", default=python_benchmark.DEFAULT_EXPECTED_COMMIT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--reset-checkout", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--python-version", default=os.environ.get("PYTHON_VERSION", "3.13"))
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--expected-snapshot", type=Path, default=DEFAULT_EXPECTED_SNAPSHOT)
    parser.add_argument("--sample-interval", type=float, default=0.02)
    parser.add_argument("--compare-python-backend", action="store_true")
    parser.add_argument("--python-backend-fallback", choices=["error", "python"], default="error")
    parser.add_argument("--min-parse-elapsed-ratio", type=float, default=1.0)
    parser.add_argument("--min-sampled-rss-ratio", type=float, default=1.0)
    parser.add_argument("--run-transform-proof", action="store_true")
    parser.add_argument("--transform-new-name", default=PYTHON_RENAMED_FUNCTION)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
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
