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
    "pkg/__init__.py": "from .api import ApiHelper as public_helper\n",
    "pkg/api.py": "from .models import Helper as ApiHelper\n",
    "pkg/models.py": "class Helper:\n    pass\n\n\ndef build():\n    return Helper()\n",
    "pkg/service.py": (
        "import requests\n"
        "import pkg.models as models\n"
        "from pkg.models import Helper\n"
        "from pkg.api import ApiHelper\n"
        "from pkg import public_helper\n"
        "\n\n"
        "def run():\n"
        "    item = Helper()\n"
        "    api = ApiHelper()\n"
        "    other = models.build()\n"
        "    public = public_helper()\n"
        "    return public, api, item, other, requests.get\n"
        "\n\n"
        "def load_plugin(name):\n"
        "    import importlib\n"
        "    return importlib.import_module(name)\n"
    ),
}

MUTATION_FILES = {
    "pkg/service.py": "import os\nimport pkg.service\n\nclass Service:\n    def run(self):\n        return os.getcwd()\n\ndef helper():\n    return Service()\n",
}
MUTATION_OUTPUT_PATHS = ["pkg/service.py"]

TYPESCRIPT_FIXTURE_FILES = {
    "src/util.ts": "export function helper(value: number) { return value; }\n",
    "src/index.ts": "export { helper as publicHelper } from './util';\n",
    "src/app.ts": (
        "import { helper } from './util';\n"
        "import { publicHelper } from './index';\n"
        "\n"
        "export function run() {\n"
        "  return helper(publicHelper(1));\n"
        "}\n"
    ),
}
TYPESCRIPT_MUTATION_FILES = {
    "src/util.ts": "export function helper(value: number) { return value; }\n",
    "src/app.ts": "import { helper } from './util';\n\nexport function run() {\n  return helper(1);\n}\n",
}
TYPESCRIPT_MUTATION_OUTPUT_PATHS = ["src/app.ts"]


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


def sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))


def import_signature(imp: Any) -> dict[str, Any]:
    return {
        "filepath": imp.filepath,
        "source": imp.source,
        "name": imp.name,
        "from_file": None if imp.from_file is None else imp.from_file.filepath,
        "resolved_symbol": node_signature(imp.resolved_symbol),
    }


def import_target_signature(imp: Any) -> dict[str, Any]:
    return {
        "filepath": imp.filepath,
        "source": imp.source,
        "name": imp.name,
        "from_file": None if imp.from_file is None else imp.from_file.filepath,
        "resolved_symbol": node_signature(imp.resolved_symbol),
    }


def export_signature(export: Any) -> dict[str, Any]:
    return {
        "filepath": export.filepath,
        "name": export.name,
        "declared_symbol": node_signature(export.declared_symbol),
        "exported_symbol": node_signature(export.exported_symbol),
        "resolved_symbol": node_signature(export.resolved_symbol),
        "is_default": export.is_default_export(),
        "is_reexport": export.is_reexport(),
    }


def resolved_target_signature(node: Any) -> dict[str, Any] | None:
    if node_type_name(getattr(node, "node_type", None)) in {"IMPORT", "EXPORT"}:
        resolved_symbol = getattr(node, "resolved_symbol", None)
        if resolved_symbol is not None:
            return node_signature(resolved_symbol)
    return node_signature(node)


def unique_sorted_signatures(items: list[dict[str, Any] | None]) -> list[dict[str, Any] | None]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return sorted(
        unique,
        key=lambda item: (
            "" if item is None else item.get("filepath") or "",
            "" if item is None else item.get("node_type") or "",
            "" if item is None else item.get("name") or "",
        ),
    )


def import_resolves_to_external(imp: Any) -> bool:
    resolved = imp.resolved_symbol
    return node_type_name(getattr(resolved, "node_type", None)) == "EXTERNAL"


def get_symbol(codebase: Any, name: str) -> Any | None:
    return codebase.get_symbol(name, optional=True)


def symbol_dependency_graph(symbols: list[Any]) -> list[dict[str, Any]]:
    return sorted_rows(
        [
            {
                "symbol": node_signature(symbol),
                "dependencies": unique_sorted_signatures(
                    [node_signature(dependency) for dependency in symbol.dependencies]
                ),
            }
            for symbol in symbols
        ]
    )


def symbol_usage_graph(symbols: list[Any]) -> list[dict[str, Any]]:
    return sorted_rows(
        [
            {
                "symbol": node_signature(symbol),
                "symbol_usages": unique_sorted_signatures(
                    [node_signature(usage) for usage in symbol.symbol_usages]
                ),
            }
            for symbol in symbols
        ]
    )


def import_usage_graph(imports: list[Any]) -> list[dict[str, Any]]:
    return sorted_rows(
        [
            {
                "import": import_signature(imp),
                "symbol_usages": unique_sorted_signatures(
                    [node_signature(usage) for usage in imp.symbol_usages]
                ),
            }
            for imp in imports
        ]
    )


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
    load_plugin = get_symbol(codebase, "load_plugin")

    if helper is None or build is None or run is None or load_plugin is None:
        missing = [
            name
            for name, symbol in (
                ("Helper", helper),
                ("build", build),
                ("run", run),
                ("load_plugin", load_plugin),
            )
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
        "imports": sorted_rows([import_signature(imp) for imp in codebase.imports]),
        "service_imports": sorted(
            (import_signature(imp) for imp in service.imports),
            key=lambda item: item["source"],
        ),
        "external_modules": sorted_signatures(codebase.external_modules),
        "symbol_dependency_graph": symbol_dependency_graph(codebase.symbols),
        "symbol_usage_graph": symbol_usage_graph(codebase.symbols),
        "import_usage_graph": import_usage_graph(codebase.imports),
        "build_dependencies": sorted_signatures(build.dependencies),
        "build_symbol_usages": sorted_signatures(build.symbol_usages),
        "helper_symbol_usages_symbols_only": sorted_signatures(helper_symbol_usages),
        "run_internal_dependencies": sorted_signatures(run_internal_dependencies),
        "run_dependencies": sorted_signatures(run_dependencies),
        "load_plugin_dependencies": sorted_signatures(load_plugin.dependencies),
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


def collect_typescript_report(codebase: Any, *, expect_blocked_graph: bool) -> dict[str, Any]:
    python_graph_blocked = False
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        python_graph_blocked = True

    app = codebase.get_file("src/app.ts")
    helper = get_symbol(codebase, "helper")
    run = get_symbol(codebase, "run")
    if helper is None or run is None:
        missing = [
            name
            for name, symbol in (("helper", helper), ("run", run))
            if symbol is None
        ]
        msg = "missing expected TypeScript symbols: " + ", ".join(missing)
        raise RuntimeError(msg)

    helper_symbol_usages = [
        usage
        for usage in helper.symbol_usages
        if node_type_name(getattr(usage, "node_type", None)) == "SYMBOL"
    ]
    report = {
        "python_graph_blocked": python_graph_blocked,
        "files": sorted(file.filepath for file in codebase.files),
        "symbols": sorted_signatures(codebase.symbols),
        "imports": sorted_rows([import_target_signature(imp) for imp in codebase.imports]),
        "app_import_targets": sorted(
            (import_target_signature(imp) for imp in app.imports),
            key=lambda item: (item["from_file"] or "", item["name"] or ""),
        ),
        "exports": sorted(
            (export_signature(export) for export in codebase.exports),
            key=lambda item: (item["filepath"], item["name"] or ""),
        ),
        "symbol_dependency_graph": symbol_dependency_graph(codebase.symbols),
        "symbol_usage_graph": symbol_usage_graph(codebase.symbols),
        "import_usage_graph": import_usage_graph(codebase.imports),
        "helper_symbol_usages_symbols_only": sorted_signatures(helper_symbol_usages),
        "run_resolved_dependency_targets": unique_sorted_signatures(
            [resolved_target_signature(dependency) for dependency in run.dependencies]
        ),
    }
    if expect_blocked_graph and not python_graph_blocked:
        msg = "expected compact Rust backend to block Python graph materialization"
        raise RuntimeError(msg)
    return report


def make_typescript_codebase_report(files: dict[str, str], *, backend: str) -> dict[str, Any]:
    from graph_sitter.codebase.factory.get_session import get_codebase_session
    from graph_sitter.configs.models.codebase import (
        CodebaseConfig,
        GraphBackend,
        RustFallbackMode,
    )
    from graph_sitter.shared.enums.programming_language import ProgrammingLanguage

    tmpdir = Path(tempfile.mkdtemp(prefix=f"graph-sitter-ts-parity-{backend}-"))
    try:
        graph_backend = GraphBackend.PYTHON if backend == "python" else GraphBackend.RUST
        config = CodebaseConfig(
            graph_backend=graph_backend,
            rust_fallback=RustFallbackMode.ERROR,
        )
        with get_codebase_session(
            tmpdir=tmpdir,
            programming_language=ProgrammingLanguage.TYPESCRIPT,
            files=files,
            config=config,
            verify_input=False,
            verify_output=False,
        ) as codebase:
            return collect_typescript_report(codebase, expect_blocked_graph=backend == "rust")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def read_outputs(root: Path, paths: list[str]) -> dict[str, str]:
    return {path: (root / path).read_text(encoding="utf-8") for path in paths}


def make_mutation_report(files: dict[str, str], *, backend: str) -> dict[str, Any]:
    from graph_sitter.codebase.factory.get_session import get_codebase_session
    from graph_sitter.configs.models.codebase import (
        CodebaseConfig,
        GraphBackend,
        RustFallbackMode,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix=f"graph-sitter-mutation-{backend}-"))
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
            sync_graph=False,
            verify_input=False,
            verify_output=False,
        ) as codebase:
            service_file = codebase.get_file("pkg/service.py")
            service_file.add_import("from typing import Any")
            codebase.imports[0].remove()
            codebase.get_class("Service").rename("Worker")
            codebase.commit(sync_graph=False)

            python_graph_blocked = False
            try:
                len(codebase.ctx.nodes)
            except RuntimeError:
                python_graph_blocked = True
            if backend == "rust" and not python_graph_blocked:
                msg = "expected compact Rust mutation flow to keep Python graph blocked"
                raise RuntimeError(msg)

        return {
            "python_graph_blocked": python_graph_blocked,
            "outputs": read_outputs(tmpdir, MUTATION_OUTPUT_PATHS),
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def make_typescript_mutation_report(files: dict[str, str], *, backend: str) -> dict[str, Any]:
    from graph_sitter.codebase.factory.get_session import get_codebase_session
    from graph_sitter.configs.models.codebase import (
        CodebaseConfig,
        GraphBackend,
        RustFallbackMode,
    )
    from graph_sitter.shared.enums.programming_language import ProgrammingLanguage

    tmpdir = Path(tempfile.mkdtemp(prefix=f"graph-sitter-ts-mutation-{backend}-"))
    try:
        graph_backend = GraphBackend.PYTHON if backend == "python" else GraphBackend.RUST
        config = CodebaseConfig(
            graph_backend=graph_backend,
            rust_fallback=RustFallbackMode.ERROR,
        )
        with get_codebase_session(
            tmpdir=tmpdir,
            programming_language=ProgrammingLanguage.TYPESCRIPT,
            files=files,
            config=config,
            sync_graph=False,
            verify_input=False,
            verify_output=False,
        ) as codebase:
            app_file = codebase.get_file("src/app.ts")
            app_file.add_import("import { describe } from 'node:test';")
            codebase.get_function("run").rename("executeRun")
            codebase.commit(sync_graph=False)

            python_graph_blocked = False
            try:
                len(codebase.ctx.nodes)
            except RuntimeError:
                python_graph_blocked = True
            if backend == "rust" and not python_graph_blocked:
                msg = "expected compact Rust TypeScript mutation flow to keep Python graph blocked"
                raise RuntimeError(msg)

        return {
            "python_graph_blocked": python_graph_blocked,
            "outputs": read_outputs(tmpdir, TYPESCRIPT_MUTATION_OUTPUT_PATHS),
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def compare_reports(python_report: dict[str, Any], rust_report: dict[str, Any]) -> dict[str, Any]:
    exact_keys = [
        "files",
        "symbols",
        "imports",
        "service_imports",
        "external_modules",
        "symbol_dependency_graph",
        "symbol_usage_graph",
        "import_usage_graph",
        "build_dependencies",
        "build_symbol_usages",
        "helper_symbol_usages_symbols_only",
        "run_internal_dependencies",
        "run_dependencies",
        "load_plugin_dependencies",
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


def compare_typescript_reports(python_report: dict[str, Any], rust_report: dict[str, Any]) -> dict[str, Any]:
    exact_keys = [
        "files",
        "symbols",
        "imports",
        "app_import_targets",
        "exports",
        "symbol_dependency_graph",
        "symbol_usage_graph",
        "import_usage_graph",
        "helper_symbol_usages_symbols_only",
        "run_resolved_dependency_targets",
    ]
    mismatches = [
        key for key in exact_keys if python_report.get(key) != rust_report.get(key)
    ]
    return {
        "exact_keys": exact_keys,
        "mismatches": mismatches,
        "known_deltas": {},
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
    python_typescript_report = make_typescript_codebase_report(TYPESCRIPT_FIXTURE_FILES, backend="python")
    rust_typescript_report = make_typescript_codebase_report(TYPESCRIPT_FIXTURE_FILES, backend="rust")
    typescript_comparison = compare_typescript_reports(python_typescript_report, rust_typescript_report)
    python_mutation_report = make_mutation_report(MUTATION_FILES, backend="python")
    rust_mutation_report = make_mutation_report(MUTATION_FILES, backend="rust")
    mutation_mismatch = python_mutation_report["outputs"] != rust_mutation_report["outputs"]
    python_typescript_mutation_report = make_typescript_mutation_report(TYPESCRIPT_MUTATION_FILES, backend="python")
    rust_typescript_mutation_report = make_typescript_mutation_report(TYPESCRIPT_MUTATION_FILES, backend="rust")
    typescript_mutation_mismatch = python_typescript_mutation_report["outputs"] != rust_typescript_mutation_report["outputs"]
    report = {
        "metadata": {
            "extension_path": str(extension_path) if extension_path else None,
            "fixture_files": sorted(FIXTURE_FILES),
            "mutation_files": sorted(MUTATION_FILES),
            "typescript_fixture_files": sorted(TYPESCRIPT_FIXTURE_FILES),
            "typescript_mutation_files": sorted(TYPESCRIPT_MUTATION_FILES),
        },
        "python": python_report,
        "rust": rust_report,
        "python_typescript": python_typescript_report,
        "rust_typescript": rust_typescript_report,
        "python_mutation": python_mutation_report,
        "rust_mutation": rust_mutation_report,
        "python_typescript_mutation": python_typescript_mutation_report,
        "rust_typescript_mutation": rust_typescript_mutation_report,
        "comparison": comparison,
        "typescript_comparison": typescript_comparison,
    }
    if comparison["mismatches"]:
        msg = "Python/Rust parity fixture mismatches: " + ", ".join(
            comparison["mismatches"]
        )
        raise RuntimeError(msg)
    if typescript_comparison["mismatches"]:
        msg = "Python/Rust TypeScript parity fixture mismatches: " + ", ".join(
            typescript_comparison["mismatches"]
        )
        raise RuntimeError(msg)
    if mutation_mismatch:
        msg = "Python/Rust mutation parity fixture mismatched file outputs"
        raise RuntimeError(msg)
    if typescript_mutation_mismatch:
        msg = "Python/Rust TypeScript mutation parity fixture mismatched file outputs"
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
    typescript_comparison = report["typescript_comparison"]
    print("Python/Rust parity fixture passed")
    print(f"exact keys: {', '.join(comparison['exact_keys'])}")
    print(f"external modules: {len(report['rust']['external_modules'])}")
    print(f"service imports: {len(report['rust']['service_imports'])}")
    print(f"mutation outputs: {len(report['rust_mutation']['outputs'])}")
    print(f"typescript exact keys: {', '.join(typescript_comparison['exact_keys'])}")
    print(f"typescript exports: {len(report['rust_typescript']['exports'])}")
    print(f"typescript mutation outputs: {len(report['rust_typescript_mutation']['outputs'])}")
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
