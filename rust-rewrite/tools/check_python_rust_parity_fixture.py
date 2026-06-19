#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from benchmark_pinned_python_repo import build_rust_extension  # noqa: E402

DEFAULT_EXTENSION_DIR = Path("/tmp/graph_sitter_py_parity_fixture")

FIXTURE_FILES = {
    "pkg/__init__.py": "from .models import Helper as public_helper\n",
    "pkg/models.py": "class Helper:\n    pass\n\n\ndef build():\n    return Helper()\n",
    "pkg/service.py": (
        "import requests\n"
        "import pkg.models as models\n"
        "from pkg.models import Helper\n"
        "from pkg import public_helper\n"
        "\n\n"
        "def run():\n"
        "    item = Helper()\n"
        "    other = models.build()\n"
        "    return public_helper(), item, other, requests.get\n"
    ),
}


def node_type_name(value: Any) -> str:
    return str(getattr(value, "name", value))


def node_signature(node: Any) -> dict[str, Any] | None:
    if node is None:
        return None
    signature = {
        "node_type": node_type_name(getattr(node, "node_type", type(node).__name__)),
        "name": getattr(node, "name", None),
        "filepath": getattr(node, "filepath", None),
    }
    if signature["node_type"] == "EXTERNAL":
        signature["source"] = getattr(node, "source", None)
    return signature


def sorted_signatures(nodes: list[Any]) -> list[dict[str, Any]]:
    return sorted(
        (node_signature(node) for node in nodes),
        key=lambda item: (
            item["filepath"] or "",
            item["node_type"],
            item["name"] or "",
            item.get("source") or "",
        ),
    )


def import_signature(imp: Any) -> dict[str, Any]:
    return {
        "source": imp.source,
        "name": imp.name,
        "from_file": None if imp.from_file is None else imp.from_file.filepath,
        "resolved_symbol": node_signature(imp.resolved_symbol),
    }


def import_resolves_to_external(imp: Any) -> bool:
    resolved = imp.resolved_symbol
    return node_type_name(getattr(resolved, "node_type", None)) == "EXTERNAL"


def get_symbol(codebase: Any, name: str) -> Any | None:
    return codebase.get_symbol(name, optional=True)


def collect_report(codebase: Any, *, expect_blocked_graph: bool) -> dict[str, Any]:
    python_graph_blocked = False
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        python_graph_blocked = True

    service = codebase.get_file("pkg/service.py")
    helper = get_symbol(codebase, "Helper")
    build = get_symbol(codebase, "build")
    run = get_symbol(codebase, "run")

    if helper is None or build is None or run is None:
        missing = [
            name
            for name, symbol in (("Helper", helper), ("build", build), ("run", run))
            if symbol is None
        ]
        msg = "missing expected symbols: " + ", ".join(missing)
        raise RuntimeError(msg)

    helper_symbol_usages = [
        usage
        for usage in helper.symbol_usages
        if node_type_name(getattr(usage, "node_type", None)) == "SYMBOL"
    ]
    run_dependencies = list(run.dependencies)
    run_internal_dependencies = [
        dependency
        for dependency in run_dependencies
        if not (
            node_type_name(getattr(dependency, "node_type", None)) == "IMPORT"
            and import_resolves_to_external(dependency)
        )
    ]

    report = {
        "python_graph_blocked": python_graph_blocked,
        "files": sorted(file.filepath for file in codebase.files),
        "symbols": sorted(
            (
                {
                    "filepath": symbol.filepath,
                    "name": symbol.name,
                    "node_type": node_type_name(symbol.node_type),
                }
                for symbol in codebase.symbols
            ),
            key=lambda item: (item["filepath"], item["node_type"], item["name"]),
        ),
        "service_imports": sorted(
            (import_signature(imp) for imp in service.imports),
            key=lambda item: item["source"],
        ),
        "external_modules": sorted_signatures(codebase.external_modules),
        "build_dependencies": sorted_signatures(build.dependencies),
        "build_symbol_usages": sorted_signatures(build.symbol_usages),
        "helper_symbol_usages_symbols_only": sorted_signatures(helper_symbol_usages),
        "run_internal_dependencies": sorted_signatures(run_internal_dependencies),
        "run_dependencies": sorted_signatures(run_dependencies),
    }
    if expect_blocked_graph and not python_graph_blocked:
        msg = "expected compact Rust backend to block Python graph materialization"
        raise RuntimeError(msg)
    return report


def make_codebase_report(files: dict[str, str], *, backend: str) -> dict[str, Any]:
    from graph_sitter.codebase.factory.get_session import get_codebase_session
    from graph_sitter.configs.models.codebase import (
        CodebaseConfig,
        GraphBackend,
        RustFallbackMode,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix=f"graph-sitter-parity-{backend}-"))
    try:
        graph_backend = GraphBackend.PYTHON if backend == "python" else GraphBackend.RUST
        config = CodebaseConfig(
            graph_backend=graph_backend,
            rust_fallback=RustFallbackMode.ERROR,
        )
        with get_codebase_session(
            tmpdir=tmpdir,
            files=files,
            config=config,
            verify_input=False,
            verify_output=False,
        ) as codebase:
            return collect_report(codebase, expect_blocked_graph=backend == "rust")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def compare_reports(python_report: dict[str, Any], rust_report: dict[str, Any]) -> dict[str, Any]:
    exact_keys = [
        "files",
        "symbols",
        "service_imports",
        "external_modules",
        "build_dependencies",
        "build_symbol_usages",
        "helper_symbol_usages_symbols_only",
        "run_internal_dependencies",
        "run_dependencies",
    ]
    mismatches = [
        key for key in exact_keys if python_report.get(key) != rust_report.get(key)
    ]
    known_deltas: dict[str, Any] = {}
    return {
        "exact_keys": exact_keys,
        "mismatches": mismatches,
        "known_deltas": known_deltas,
    }


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    extension_path = None
    if not args.skip_build_extension:
        extension_path = build_rust_extension(args.extension_dir, timeout=args.timeout)
    if str(args.extension_dir) not in sys.path:
        sys.path.insert(0, str(args.extension_dir))

    python_report = make_codebase_report(FIXTURE_FILES, backend="python")
    rust_report = make_codebase_report(FIXTURE_FILES, backend="rust")
    comparison = compare_reports(python_report, rust_report)
    report = {
        "metadata": {
            "extension_path": str(extension_path) if extension_path else None,
            "fixture_files": sorted(FIXTURE_FILES),
        },
        "python": python_report,
        "rust": rust_report,
        "comparison": comparison,
    }
    if comparison["mismatches"]:
        msg = "Python/Rust parity fixture mismatches: " + ", ".join(
            comparison["mismatches"]
        )
        raise RuntimeError(msg)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a representative Python fixture through the Python backend and compact Rust backend."
    )
    parser.add_argument(
        "--extension-dir",
        type=Path,
        default=DEFAULT_EXTENSION_DIR,
        help="Directory for the built PyO3 extension module.",
    )
    parser.add_argument(
        "--skip-build-extension",
        action="store_true",
        help="Reuse an existing graph_sitter_py extension in --extension-dir.",
    )
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    return parser.parse_args()


def print_human(report: dict[str, Any]) -> None:
    comparison = report["comparison"]
    print("Python/Rust parity fixture passed")
    print(f"exact keys: {', '.join(comparison['exact_keys'])}")
    print(f"external modules: {len(report['rust']['external_modules'])}")
    print(f"service imports: {len(report['rust']['service_imports'])}")
    print(f"known deltas: {len(comparison['known_deltas'])}")


def main() -> int:
    args = parse_args()
    report = make_report(args)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
