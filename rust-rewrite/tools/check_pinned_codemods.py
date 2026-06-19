#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import benchmark_pinned_python_repo as python_benchmark  # noqa: E402
import benchmark_pinned_typescript_repo as typescript_benchmark  # noqa: E402

from codemods.codemod import Codemod  # noqa: E402

DEFAULT_CACHE_DIR = Path("/tmp/graph-sitter-pinned-repos")
DEFAULT_EXTENSION_DIR = Path("/tmp/graph_sitter_py_pinned_codemods")

PYTHON_TARGET_FILE = "airflow/__init__.py"
PYTHON_IMPORTED_LINE = "from typing import Any"
PYTHON_RENAMED_FUNCTION = "__getattr_rust_proof__"

TYPESCRIPT_TARGET_FILE = "packages/next/src/client/components/app-router-announcer.tsx"
TYPESCRIPT_USAGE_FILE = "packages/next/src/client/components/app-router.tsx"
TYPESCRIPT_IMPORTED_LINE = "import { act } from 'react-dom/test-utils';"
TYPESCRIPT_RENAMED_FUNCTION = "AppRouterAnnouncerProof"


def run(command: list[str], *, cwd: Path, timeout: int | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        check=True,
        text=True,
        capture_output=True,
    )


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


def current_rss_bytes() -> int:
    import psutil

    return int(psutil.Process(os.getpid()).memory_info().rss)


def memory_sample(label: str) -> dict[str, float | str]:
    return {
        "label": label,
        "rss_mb": round(bytes_to_mb(current_rss_bytes()), 3),
        "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
    }


def large_cache_materialization_report(backend: Any) -> dict[str, bool]:
    return {
        "files": backend._files is not None,
        "symbols": backend._symbols is not None,
        "imports": backend._imports is not None,
        "exports": backend._exports is not None,
        "references": backend._references is not None,
        "external_references": backend._external_references is not None,
        "dependencies": backend._dependencies is not None,
        "file_handles": backend._file_handles is not None,
        "symbol_handles": backend._symbol_handles is not None,
        "import_handles": backend._import_handles is not None,
        "export_handles": backend._export_handles is not None,
        "external_module_handles": backend._external_module_handles is not None,
    }


def prepare_repo(
    *,
    name: str,
    repo_url: str,
    ref: str,
    expected_commit: str,
    cache_dir: Path,
    reset_checkout: bool,
    skip_fetch: bool,
    timeout: int,
    prepare: Callable[[argparse.Namespace], tuple[Path, str]],
) -> tuple[Path, str]:
    repo_args = argparse.Namespace(
        name=name,
        repo_url=repo_url,
        ref=ref,
        expected_commit=expected_commit,
        cache_dir=cache_dir,
        reset_checkout=reset_checkout,
        skip_fetch=skip_fetch,
        timeout=timeout,
    )
    return prepare(repo_args)


def clone_mutable_checkout(
    cache_repo: Path,
    commit: str,
    *,
    prefix: str,
    repo_url: str,
    timeout: int,
) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tempdir = tempfile.TemporaryDirectory(prefix=f"graph-sitter-{prefix}-codemod-")
    checkout = Path(tempdir.name) / "repo"
    run(["git", "clone", "--shared", "--no-checkout", str(cache_repo), str(checkout)], cwd=REPO_ROOT, timeout=timeout)
    run(["git", "remote", "set-url", "origin", repo_url], cwd=checkout, timeout=timeout)
    run(["git", "checkout", "--detach", commit], cwd=checkout, timeout=timeout)
    return tempdir, checkout


def git_status(checkout: Path, *, timeout: int) -> list[str]:
    result = run(["git", "status", "--porcelain"], cwd=checkout, timeout=timeout)
    return [line for line in result.stdout.splitlines() if line]


def python_graph_is_blocked(codebase: Any) -> bool:
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        return True
    return False


def build_codebase(checkout: Path, *, language: str) -> Any:
    from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
    from graph_sitter.core.codebase import Codebase

    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)
    return Codebase(str(checkout), language=language, config=config)


def run_airflow_codemod(checkout: Path, *, timeout: int) -> dict[str, Any]:
    memory_samples = [memory_sample("python_start")]

    construct_start = time.perf_counter()
    codebase = build_codebase(checkout, language="python")
    construct_wall = time.perf_counter() - construct_start
    memory_samples.append(memory_sample("python_after_codebase_construct"))

    graph_blocked_before = python_graph_is_blocked(codebase)
    memory_samples.append(memory_sample("python_after_graph_block_check"))
    backend = codebase.ctx.rust_index
    assert backend is not None

    def execute(mod_codebase: Any) -> None:
        target_file = mod_codebase.get_file(PYTHON_TARGET_FILE)
        target_file.add_import(PYTHON_IMPORTED_LINE)
        target_file.get_function("__getattr__").rename(PYTHON_RENAMED_FUNCTION)

    codemod = Codemod(name="rust-pinned-airflow-import-rename", execute=execute)
    codemod_start = time.perf_counter()
    codemod.execute(codebase)
    codebase.commit(sync_graph=False)
    codemod_wall = time.perf_counter() - codemod_start
    memory_samples.append(memory_sample("python_after_codemod_commit"))

    graph_blocked_after = python_graph_is_blocked(codebase)
    modified_content = (checkout / PYTHON_TARGET_FILE).read_text(encoding="utf-8")
    status = git_status(checkout, timeout=timeout)
    cache_materialization = large_cache_materialization_report(backend)

    assertions = {
        "added_import": PYTHON_IMPORTED_LINE in modified_content,
        "renamed_declaration": f"def {PYTHON_RENAMED_FUNCTION}(name: str):" in modified_content,
        "removed_original_declaration": "def __getattr__(name: str):" not in modified_content,
        "only_target_file_modified": status == [f" M {PYTHON_TARGET_FILE}"],
        "python_graph_blocked_before": graph_blocked_before,
        "python_graph_blocked_after": graph_blocked_after,
        "large_caches_cold": not any(cache_materialization.values()),
    }

    return {
        "suite": "python",
        "repo": "apache-airflow-2.10.5",
        "target_file": PYTHON_TARGET_FILE,
        "codemod": codemod.name,
        "timings": {
            "codebase_construct_wall_seconds": round(construct_wall, 6),
            "codemod_commit_wall_seconds": round(codemod_wall, 6),
        },
        "rss_samples": memory_samples,
        "git_status": status,
        "assertions": assertions,
        "large_cache_materialization": cache_materialization,
    }


def run_nextjs_codemod(checkout: Path, *, timeout: int) -> dict[str, Any]:
    memory_samples = [memory_sample("typescript_start")]

    construct_start = time.perf_counter()
    codebase = build_codebase(checkout, language="typescript")
    construct_wall = time.perf_counter() - construct_start
    memory_samples.append(memory_sample("typescript_after_codebase_construct"))

    graph_blocked_before = python_graph_is_blocked(codebase)
    memory_samples.append(memory_sample("typescript_after_graph_block_check"))
    backend = codebase.ctx.rust_index
    assert backend is not None

    def execute(mod_codebase: Any) -> None:
        target_file = mod_codebase.get_file(TYPESCRIPT_TARGET_FILE)
        target_file.add_import(TYPESCRIPT_IMPORTED_LINE)
        target_file.get_function("AppRouterAnnouncer").rename(TYPESCRIPT_RENAMED_FUNCTION)

    codemod = Codemod(name="rust-pinned-nextjs-import-rename", execute=execute)
    codemod_start = time.perf_counter()
    codemod.execute(codebase)
    codebase.commit(sync_graph=False)
    codemod_wall = time.perf_counter() - codemod_start
    memory_samples.append(memory_sample("typescript_after_codemod_commit"))

    graph_blocked_after = python_graph_is_blocked(codebase)
    modified_content = (checkout / TYPESCRIPT_TARGET_FILE).read_text(encoding="utf-8")
    usage_content = (checkout / TYPESCRIPT_USAGE_FILE).read_text(encoding="utf-8")
    status = git_status(checkout, timeout=timeout)
    cache_materialization = large_cache_materialization_report(backend)
    expected_status = {
        f" M {TYPESCRIPT_TARGET_FILE}",
        f" M {TYPESCRIPT_USAGE_FILE}",
    }

    assertions = {
        "added_import": TYPESCRIPT_IMPORTED_LINE in modified_content,
        "renamed_declaration": f"export function {TYPESCRIPT_RENAMED_FUNCTION}" in modified_content,
        "removed_original_declaration": "export function AppRouterAnnouncer(" not in modified_content,
        "rewrote_importing_usage": TYPESCRIPT_RENAMED_FUNCTION in usage_content,
        "only_expected_files_modified": set(status) == expected_status,
        "python_graph_blocked_before": graph_blocked_before,
        "python_graph_blocked_after": graph_blocked_after,
        "large_caches_cold": not any(cache_materialization.values()),
    }

    return {
        "suite": "typescript",
        "repo": "next.js-v15.0.0",
        "target_file": TYPESCRIPT_TARGET_FILE,
        "codemod": codemod.name,
        "timings": {
            "codebase_construct_wall_seconds": round(construct_wall, 6),
            "codemod_commit_wall_seconds": round(codemod_wall, 6),
        },
        "rss_samples": memory_samples,
        "git_status": status,
        "assertions": assertions,
        "large_cache_materialization": cache_materialization,
    }


def run_python_suite(args: argparse.Namespace) -> dict[str, Any]:
    cache_repo, commit = prepare_repo(
        name=python_benchmark.DEFAULT_REPO_NAME,
        repo_url=python_benchmark.DEFAULT_REPO_URL,
        ref=python_benchmark.DEFAULT_REF,
        expected_commit=python_benchmark.DEFAULT_EXPECTED_COMMIT,
        cache_dir=args.cache_dir,
        reset_checkout=args.reset_checkout,
        skip_fetch=args.skip_fetch,
        timeout=args.timeout,
        prepare=python_benchmark.prepare_pinned_repo,
    )
    tempdir, checkout = clone_mutable_checkout(
        cache_repo,
        commit,
        prefix="airflow",
        repo_url=python_benchmark.DEFAULT_REPO_URL,
        timeout=args.timeout,
    )
    with tempdir:
        report = run_airflow_codemod(checkout, timeout=args.timeout)
        report["metadata"] = {
            "repo_url": python_benchmark.DEFAULT_REPO_URL,
            "ref": python_benchmark.DEFAULT_REF,
            "commit": commit,
            "cache_checkout": str(cache_repo),
            "mutable_checkout": str(checkout),
        }
        return report


def run_typescript_suite(args: argparse.Namespace) -> dict[str, Any]:
    cache_repo, commit = prepare_repo(
        name=typescript_benchmark.DEFAULT_REPO_NAME,
        repo_url=typescript_benchmark.DEFAULT_REPO_URL,
        ref=typescript_benchmark.DEFAULT_REF,
        expected_commit=typescript_benchmark.DEFAULT_EXPECTED_COMMIT,
        cache_dir=args.cache_dir,
        reset_checkout=args.reset_checkout,
        skip_fetch=args.skip_fetch,
        timeout=args.timeout,
        prepare=typescript_benchmark.prepare_pinned_repo,
    )
    tempdir, checkout = clone_mutable_checkout(
        cache_repo,
        commit,
        prefix="nextjs",
        repo_url=typescript_benchmark.DEFAULT_REPO_URL,
        timeout=args.timeout,
    )
    with tempdir:
        report = run_nextjs_codemod(checkout, timeout=args.timeout)
        report["metadata"] = {
            "repo_url": typescript_benchmark.DEFAULT_REPO_URL,
            "ref": typescript_benchmark.DEFAULT_REF,
            "commit": commit,
            "cache_checkout": str(cache_repo),
            "mutable_checkout": str(checkout),
        }
        return report


def validate_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    failures: list[str] = []
    for suite in report["suites"]:
        failed_assertions = [name for name, passed in suite["assertions"].items() if not passed]
        if failed_assertions:
            failures.append(f"{suite['suite']} assertions failed: {', '.join(failed_assertions)}")
        timings = suite["timings"]
        if timings["codebase_construct_wall_seconds"] > args.max_construct_wall_seconds:
            failures.append(
                f"{suite['suite']} construct wall {timings['codebase_construct_wall_seconds']}s "
                f"exceeds {args.max_construct_wall_seconds}s"
            )
        if timings["codemod_commit_wall_seconds"] > args.max_codemod_wall_seconds:
            failures.append(
                f"{suite['suite']} codemod wall {timings['codemod_commit_wall_seconds']}s "
                f"exceeds {args.max_codemod_wall_seconds}s"
            )
        max_rss = max(float(sample["max_rss_mb"]) for sample in suite["rss_samples"])
        if max_rss > args.max_rss_mb:
            failures.append(f"{suite['suite']} max RSS {max_rss} MB exceeds {args.max_rss_mb} MB")

    if failures:
        raise RuntimeError("; ".join(failures))


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    extension_path = None
    if not args.skip_build_extension:
        extension_path = python_benchmark.build_rust_extension(args.extension_dir, timeout=args.timeout)
    if str(args.extension_dir) not in sys.path:
        sys.path.insert(0, str(args.extension_dir))

    suites: list[dict[str, Any]] = []
    if args.suite in {"all", "python"}:
        suites.append(run_python_suite(args))
    if args.suite in {"all", "typescript"}:
        suites.append(run_typescript_suite(args))

    report = {
        "metadata": {
            "suite": args.suite,
            "extension_path": str(extension_path) if extension_path else None,
            "extension_dir": str(args.extension_dir),
            "cache_dir": str(args.cache_dir),
        },
        "suites": suites,
    }
    validate_report(report, args)
    return report


def print_human(report: dict[str, Any]) -> None:
    print(f"suite: {report['metadata']['suite']}")
    print(f"extension_dir: {report['metadata']['extension_dir']}")
    for suite in report["suites"]:
        timings = suite["timings"]
        max_rss = max(float(sample["max_rss_mb"]) for sample in suite["rss_samples"])
        print(
            f"{suite['suite']} {suite['repo']}: "
            f"construct={timings['codebase_construct_wall_seconds']:.3f}s "
            f"codemod={timings['codemod_commit_wall_seconds']:.3f}s "
            f"max_rss={max_rss:.1f} MB "
            f"modified={', '.join(suite['git_status'])}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run graph-free compact Rust codemod smoke checks on pinned Airflow and Next.js checkouts."
    )
    parser.add_argument("--suite", choices=["all", "python", "typescript"], default="all")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Directory for reusable pinned checkouts.")
    parser.add_argument("--extension-dir", type=Path, default=DEFAULT_EXTENSION_DIR, help="Directory for the built PyO3 extension module.")
    parser.add_argument("--reset-checkout", action="store_true", help="Delete and recreate cached pinned checkouts before running.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch before checkout; useful for offline reruns with FETCH_HEAD present.")
    parser.add_argument("--skip-build-extension", action="store_true", help="Reuse an existing graph_sitter_py extension in --extension-dir.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for clone/build/check child commands.")
    parser.add_argument("--max-construct-wall-seconds", type=float, default=20.0, help="Fail if any Rust Codebase construction exceeds this ceiling.")
    parser.add_argument("--max-codemod-wall-seconds", type=float, default=10.0, help="Fail if any codemod execute+commit exceeds this ceiling.")
    parser.add_argument("--max-rss-mb", type=float, default=1000.0, help="Fail if process max RSS exceeds this ceiling.")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
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
