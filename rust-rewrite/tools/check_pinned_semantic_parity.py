#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import benchmark_pinned_python_repo as python_benchmark  # noqa: E402
import benchmark_pinned_typescript_repo as typescript_benchmark  # noqa: E402
from benchmark_pinned_python_repo import parse_json_output  # noqa: E402

DEFAULT_CACHE_DIR = Path("/tmp/graph-sitter-pinned-repos")
DEFAULT_EXTENSION_DIR = Path("/tmp/graph_sitter_py_pinned_semantic_parity")

AIRFLOW_INIT_FILE = "airflow/__init__.py"
AIRFLOW_MANAGER_FILE = "airflow/dag_processing/manager.py"
NEXTJS_ANNOUNCER_FILE = "packages/next/src/client/components/app-router-announcer.tsx"


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        command_text = " ".join(command)
        msg = f"command failed with exit code {result.returncode}: {command_text}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        raise RuntimeError(msg)
    return result


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 3)


def ratio_at_least(value: Any, minimum: float) -> bool:
    return isinstance(value, int | float) and value >= minimum


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


def node_type_name(value: Any) -> str:
    return str(getattr(value, "name", value))


def node_signature(node: Any) -> dict[str, Any] | None:
    if node is None:
        return None
    node_type = node_type_name(getattr(node, "node_type", type(node).__name__))
    signature = {
        "filepath": getattr(node, "filepath", None),
        "name": getattr(node, "name", None),
        "node_type": node_type,
    }
    source = getattr(node, "source", None)
    if node_type in {"IMPORT", "EXPORT", "EXTERNAL"} and source is not None:
        signature["source"] = source
    return signature


def file_signature(file: Any) -> dict[str, Any]:
    return {
        "filepath": file.filepath,
        "name": file.name,
        "node_type": node_type_name(getattr(file, "node_type", type(file).__name__)),
    }


def import_signature(imp: Any) -> dict[str, Any]:
    return {
        "filepath": imp.filepath,
        "from_file": None if imp.from_file is None else imp.from_file.filepath,
        "name": imp.name,
        "resolved_symbol": node_signature(imp.resolved_symbol),
        "source": imp.source,
    }


def find_import(file: Any, lookup: str) -> Any:
    import_handle = file.get_import(lookup)
    if import_handle is not None:
        return import_handle
    for candidate in file.imports:
        if candidate.source == lookup or candidate.name == lookup:
            return candidate
    msg = f"could not find import {lookup!r} in {file.filepath}"
    raise RuntimeError(msg)


def export_signature(export: Any) -> dict[str, Any]:
    return {
        "declared_symbol": node_signature(export.declared_symbol),
        "exported_symbol": node_signature(export.exported_symbol),
        "filepath": export.filepath,
        "is_default": export.is_default_export(),
        "is_reexport": export.is_reexport(),
        "name": export.name,
        "resolved_symbol": node_signature(export.resolved_symbol),
    }


def dependency_signature(handle: Any) -> dict[str, Any] | None:
    if node_type_name(getattr(handle, "node_type", None)) in {"IMPORT", "EXPORT"}:
        resolved = getattr(handle, "resolved_symbol", None)
        if resolved is not None:
            signature = node_signature(handle)
            assert signature is not None
            signature["resolved_symbol"] = node_signature(resolved)
            return signature
    return node_signature(handle)


def sort_key(item: dict[str, Any] | None) -> tuple[str, str, str, str]:
    if item is None:
        return ("", "", "", "")
    return (
        item.get("filepath") or "",
        item.get("node_type") or "",
        item.get("name") or "",
        item.get("source") or "",
    )


def sorted_signatures(items: list[dict[str, Any] | None]) -> list[dict[str, Any] | None]:
    return sorted(items, key=sort_key)


def unique_sorted_signatures(items: list[dict[str, Any] | None]) -> list[dict[str, Any] | None]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return sorted_signatures(unique)


def max_sample_rss_mb(report: dict[str, Any]) -> float | None:
    samples = report.get("rss_samples", [])
    if not isinstance(samples, list) or not samples:
        return None
    values = [float(sample["max_rss_mb"]) for sample in samples if isinstance(sample, dict) and "max_rss_mb" in sample]
    return max(values) if values else None


def graph_is_blocked(codebase: Any) -> bool:
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        return True
    return False


def build_codebase(repo: Path, *, backend: str, language: str, extension_dir: Path) -> Any:
    if backend == "rust" and str(extension_dir) not in sys.path:
        sys.path.insert(0, str(extension_dir))

    from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
    from graph_sitter.core.codebase import Codebase

    graph_backend = GraphBackend.PYTHON if backend == "python" else GraphBackend.RUST
    config = CodebaseConfig(graph_backend=graph_backend, rust_fallback=RustFallbackMode.ERROR)
    return Codebase(str(repo), language=language, config=config)


def collect_airflow_report(repo: Path, *, backend: str, extension_dir: Path) -> dict[str, Any]:
    memory_samples = [memory_sample("start")]
    start = time.perf_counter()
    codebase = build_codebase(repo, backend=backend, language="python", extension_dir=extension_dir)
    wall_seconds = time.perf_counter() - start
    memory_samples.append(memory_sample("after_codebase_construct"))

    python_graph_blocked = graph_is_blocked(codebase)
    memory_samples.append(memory_sample("after_graph_block_check"))

    init_file = codebase.get_file(AIRFLOW_INIT_FILE)
    manager_file = codebase.get_file(AIRFLOW_MANAGER_FILE)
    getattr_function = init_file.get_function("__getattr__")
    provider_validator = codebase.get_function("_create_provider_info_schema_validator")
    airflow_models_import = manager_file.get_import("airflow.models")

    report = {
        "backend": backend,
        "python_graph_blocked": python_graph_blocked,
        "timings": {"codebase_construct_wall_seconds": round(wall_seconds, 6)},
        "rss_samples": memory_samples,
        "known_files": {
            "airflow_init": file_signature(init_file),
            "dag_processing_manager": file_signature(manager_file),
        },
        "global_function": node_signature(provider_validator),
        "airflow_init_import_os": import_signature(find_import(init_file, "import os")),
        "airflow_init_resolve_getattr": sorted_signatures([node_signature(node) for node in init_file.resolve_name("__getattr__")]),
        "airflow_init_resolve_os": node_signature(init_file.resolve_attribute("os")),
        "airflow_init_get_node_os": node_signature(init_file.get_node_by_name("os")),
        "module_import_attribute_resolution": node_signature(airflow_models_import.resolve_attribute("DagModel")),
        "getattr_dependencies": sorted_signatures([dependency_signature(handle) for handle in getattr_function.dependencies]),
    }
    if backend == "rust" and not python_graph_blocked:
        msg = "expected Rust Airflow semantic parity run to keep Python graph blocked"
        raise RuntimeError(msg)
    return report


def collect_nextjs_report(repo: Path, *, backend: str, extension_dir: Path) -> dict[str, Any]:
    memory_samples = [memory_sample("start")]
    start = time.perf_counter()
    codebase = build_codebase(repo, backend=backend, language="typescript", extension_dir=extension_dir)
    wall_seconds = time.perf_counter() - start
    memory_samples.append(memory_sample("after_codebase_construct"))

    python_graph_blocked = graph_is_blocked(codebase)
    memory_samples.append(memory_sample("after_graph_block_check"))

    announcer_file = codebase.get_file(NEXTJS_ANNOUNCER_FILE)
    announcer = codebase.get_function("AppRouterAnnouncer")
    announcer_export = announcer_file.get_export("AppRouterAnnouncer")

    report = {
        "backend": backend,
        "python_graph_blocked": python_graph_blocked,
        "timings": {"codebase_construct_wall_seconds": round(wall_seconds, 6)},
        "rss_samples": memory_samples,
        "announcer_file": file_signature(announcer_file),
        "announcer_function": node_signature(announcer),
        "announcer_export": export_signature(announcer_export),
        "announcer_imports": sorted(
            (import_signature(imp) for imp in announcer_file.imports),
            key=lambda item: (item["source"], item["name"] or ""),
        ),
        "announcer_dependencies": unique_sorted_signatures([dependency_signature(handle) for handle in announcer.dependencies]),
        "announcer_import_dependencies": unique_sorted_signatures(
            [dependency_signature(handle) for handle in announcer.dependencies if node_type_name(getattr(handle, "node_type", None)) == "IMPORT"]
        ),
        "announcer_symbol_usages": unique_sorted_signatures([node_signature(handle) for handle in announcer.symbol_usages]),
    }
    if backend == "rust" and not python_graph_blocked:
        msg = "expected Rust Next.js semantic parity run to keep Python graph blocked"
        raise RuntimeError(msg)
    return report


def collect_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_path)
    if args.suite == "python":
        return collect_airflow_report(repo, backend=args.backend, extension_dir=args.extension_dir)
    if args.suite == "typescript":
        return collect_nextjs_report(repo, backend=args.backend, extension_dir=args.extension_dir)
    msg = f"unsupported collect suite: {args.suite}"
    raise ValueError(msg)


def prepare_repo(
    *,
    args: argparse.Namespace,
    suite: str,
) -> tuple[Path, str]:
    if suite == "python":
        repo_args = argparse.Namespace(
            name=python_benchmark.DEFAULT_REPO_NAME,
            repo_url=python_benchmark.DEFAULT_REPO_URL,
            ref=python_benchmark.DEFAULT_REF,
            expected_commit=python_benchmark.DEFAULT_EXPECTED_COMMIT,
            cache_dir=args.cache_dir,
            reset_checkout=args.reset_checkout,
            skip_fetch=args.skip_fetch,
            timeout=args.timeout,
        )
        return python_benchmark.prepare_pinned_repo(repo_args)
    repo_args = argparse.Namespace(
        name=typescript_benchmark.DEFAULT_REPO_NAME,
        repo_url=typescript_benchmark.DEFAULT_REPO_URL,
        ref=typescript_benchmark.DEFAULT_REF,
        expected_commit=typescript_benchmark.DEFAULT_EXPECTED_COMMIT,
        cache_dir=args.cache_dir,
        reset_checkout=args.reset_checkout,
        skip_fetch=args.skip_fetch,
        timeout=args.timeout,
    )
    return typescript_benchmark.prepare_pinned_repo(repo_args)


def collect_backend_report(
    *,
    suite: str,
    backend: str,
    repo: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--collect",
        "--suite",
        suite,
        "--backend",
        backend,
        "--repo-path",
        str(repo),
        "--extension-dir",
        str(args.extension_dir),
        "--json",
    ]
    result = run(command, cwd=REPO_ROOT, timeout=args.timeout)
    return parse_json_output(result.stdout)


def compare_suite(python_report: dict[str, Any], rust_report: dict[str, Any], *, suite: str) -> dict[str, Any]:
    if suite == "python":
        exact_keys = [
            "known_files",
            "global_function",
            "airflow_init_import_os",
            "airflow_init_resolve_getattr",
            "airflow_init_resolve_os",
            "airflow_init_get_node_os",
            "getattr_dependencies",
        ]
        known_delta_keys = ["module_import_attribute_resolution"]
        expected_known_deltas = {
            "module_import_attribute_resolution": {
                "python": None,
                "rust": {
                    "filepath": "airflow/models/__init__.py",
                    "name": "DagModel",
                    "node_type": "IMPORT",
                    "source": "from airflow.models.dag import DAG, DagModel, DagTag",
                },
            }
        }
    else:
        exact_keys = [
            "announcer_file",
            "announcer_function",
            "announcer_export",
            "announcer_imports",
            "announcer_dependencies",
            "announcer_import_dependencies",
            "announcer_symbol_usages",
        ]
        known_delta_keys = []
        expected_known_deltas = {}
    mismatches = [key for key in exact_keys if python_report.get(key) != rust_report.get(key)]
    known_deltas = {
        key: {
            "python": python_report.get(key),
            "rust": rust_report.get(key),
        }
        for key in known_delta_keys
        if python_report.get(key) != rust_report.get(key)
    }
    if known_deltas != expected_known_deltas:
        mismatches.append("known_deltas")
    python_timing = python_report.get("timings", {}).get("codebase_construct_wall_seconds")
    rust_timing = rust_report.get("timings", {}).get("codebase_construct_wall_seconds")
    performance = {
        "wall_ratio": ratio(python_timing, rust_timing),
        "rss_ratio": ratio(max_sample_rss_mb(python_report), max_sample_rss_mb(rust_report)),
    }
    return {
        "exact_keys": exact_keys,
        "expected_known_deltas": expected_known_deltas,
        "known_deltas": known_deltas,
        "mismatches": mismatches,
        "performance": performance,
    }


def run_suite(args: argparse.Namespace, suite: str) -> dict[str, Any]:
    repo, commit = prepare_repo(args=args, suite=suite)
    python_report = collect_backend_report(suite=suite, backend="python", repo=repo, args=args)
    rust_report = collect_backend_report(suite=suite, backend="rust", repo=repo, args=args)
    comparison = compare_suite(python_report, rust_report, suite=suite)
    if comparison["mismatches"]:
        msg = f"{suite} pinned semantic parity mismatches: " + ", ".join(comparison["mismatches"])
        raise RuntimeError(msg)
    performance = comparison["performance"]
    failures = []
    if not ratio_at_least(performance["wall_ratio"], args.min_wall_ratio):
        failures.append(f"wall ratio {performance['wall_ratio']}x is below {args.min_wall_ratio}x")
    if not ratio_at_least(performance["rss_ratio"], args.min_rss_ratio):
        failures.append(f"RSS ratio {performance['rss_ratio']}x is below {args.min_rss_ratio}x")
    if failures:
        msg = f"{suite} pinned semantic parity performance failed: " + "; ".join(failures)
        raise RuntimeError(msg)
    return {
        "suite": suite,
        "metadata": {
            "repo": str(repo),
            "commit": commit,
        },
        "python": python_report,
        "rust": rust_report,
        "comparison": comparison,
    }


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    extension_path = None
    if not args.skip_build_extension:
        extension_path = python_benchmark.build_rust_extension(args.extension_dir, timeout=args.timeout)
    if str(args.extension_dir) not in sys.path:
        sys.path.insert(0, str(args.extension_dir))

    suites = []
    if args.suite in {"all", "python"}:
        suites.append(run_suite(args, "python"))
    if args.suite in {"all", "typescript"}:
        suites.append(run_suite(args, "typescript"))

    return {
        "metadata": {
            "suite": args.suite,
            "extension_path": str(extension_path) if extension_path else None,
            "extension_dir": str(args.extension_dir),
            "cache_dir": str(args.cache_dir),
        },
        "suites": suites,
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"suite: {report['metadata']['suite']}")
    print(f"extension_dir: {report['metadata']['extension_dir']}")
    for suite in report["suites"]:
        python_timing = suite["python"]["timings"]["codebase_construct_wall_seconds"]
        rust_timing = suite["rust"]["timings"]["codebase_construct_wall_seconds"]
        python_max_rss = max(float(sample["max_rss_mb"]) for sample in suite["python"]["rss_samples"])
        rust_max_rss = max(float(sample["max_rss_mb"]) for sample in suite["rust"]["rss_samples"])
        print(
            f"{suite['suite']}: exact={', '.join(suite['comparison']['exact_keys'])} "
            f"known_deltas={len(suite['comparison']['known_deltas'])} "
            f"python={python_timing:.3f}s/{python_max_rss:.1f} MB "
            f"rust={rust_timing:.3f}s/{rust_max_rss:.1f} MB "
            f"ratios={suite['comparison']['performance']['wall_ratio']}x/"
            f"{suite['comparison']['performance']['rss_ratio']}x"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare selected pinned Airflow and Next.js graph semantics between Python and compact Rust backends.")
    parser.add_argument("--suite", choices=["all", "python", "typescript"], default="all")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Directory for reusable pinned checkouts.")
    parser.add_argument("--extension-dir", type=Path, default=DEFAULT_EXTENSION_DIR, help="Directory for the built PyO3 extension module.")
    parser.add_argument("--reset-checkout", action="store_true", help="Delete and recreate cached pinned checkouts before running.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not fetch before checkout; useful for offline reruns with FETCH_HEAD present.")
    parser.add_argument("--skip-build-extension", action="store_true", help="Reuse an existing graph_sitter_py extension in --extension-dir.")
    parser.add_argument("--min-wall-ratio", type=float, default=1.0, help="Fail unless Python wall time divided by Rust wall time is at least this value.")
    parser.add_argument("--min-rss-ratio", type=float, default=1.0, help="Fail unless Python max RSS divided by Rust max RSS is at least this value.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for clone/build/check child commands.")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
    parser.add_argument("--collect", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--backend", choices=["python", "rust"], help=argparse.SUPPRESS)
    parser.add_argument("--repo-path", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.collect:
        if args.backend is None or args.repo_path is None:
            msg = "--collect requires --backend and --repo-path"
            raise ValueError(msg)
        report = collect_report(args)
    else:
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
