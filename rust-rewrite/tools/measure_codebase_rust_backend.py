#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode  # noqa: E402
from graph_sitter.core.codebase import Codebase  # noqa: E402


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


def make_report(repo: Path, *, language: str) -> dict:
    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)
    start = time.perf_counter()
    codebase = Codebase(str(repo), language=language, config=config)
    wall = time.perf_counter() - start
    python_graph_blocked = False
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        python_graph_blocked = True

    summary = codebase.rust_index_summary
    return {
        "metadata": {
            "repo_path": str(repo),
            "language": language,
            "python": sys.version,
            "platform": platform.platform(),
            "python_graph_blocked": python_graph_blocked,
        },
        "totals": {
            "wall_seconds": round(wall, 6),
            "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
        },
        "summary": {
            "files": summary.files,
            "symbols": summary.symbols,
            "classes": summary.classes,
            "functions": summary.functions,
            "global_variables": summary.global_variables,
            "imports": summary.imports,
            "import_resolutions": summary.import_resolutions,
            "references": summary.references,
            "dependencies": summary.dependencies,
            "bytes": summary.bytes,
            "lines": summary.lines,
            "files_with_errors": summary.files_with_errors,
        },
        "records": {
            "rust_files": len(codebase.rust_files),
            "rust_symbols": len(codebase.rust_symbols),
            "rust_classes": len(codebase.rust_classes),
            "rust_functions": len(codebase.rust_functions),
            "rust_global_vars": len(codebase.rust_global_vars),
            "rust_imports": len(codebase.rust_imports),
            "rust_import_resolutions": len(codebase.rust_import_resolutions),
            "rust_references": len(codebase.rust_references),
            "rust_dependencies": len(codebase.rust_dependencies),
        },
        "compat_handles": {
            "files": len(codebase.files),
            "symbols": len(codebase.symbols),
            "classes": len(codebase.classes),
            "functions": len(codebase.functions),
            "global_vars": len(codebase.global_vars),
            "interfaces": len(codebase.interfaces),
            "types": len(codebase.types),
            "imports": len(codebase.imports),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure Codebase construction with the opt-in compact Rust backend.")
    parser.add_argument("repo", nargs="?", default=".", help="Path to the repository to index.")
    parser.add_argument("--language", choices=["python", "typescript"], default="python", help="Codebase language to index.")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
    return parser.parse_args()


def print_human(report: dict) -> None:
    totals = report["totals"]
    summary = report["summary"]
    records = report["records"]
    compat_handles = report["compat_handles"]
    print(f"repo: {report['metadata']['repo_path']}")
    print(f"language: {report['metadata']['language']}")
    print(f"rust Codebase: wall={totals['wall_seconds']:.3f}s max_rss={totals['max_rss_mb']:.1f} MB")
    print(f"python graph blocked: {report['metadata']['python_graph_blocked']}")
    print(
        "summary: "
        f"files={summary['files']} "
        f"symbols={summary['symbols']} "
        f"global_variables={summary['global_variables']} "
        f"imports={summary['imports']} "
        f"import_resolutions={summary['import_resolutions']} "
        f"references={summary['references']} "
        f"dependencies={summary['dependencies']}"
    )
    print(
        "records: "
        f"files={records['rust_files']} "
        f"symbols={records['rust_symbols']} "
        f"imports={records['rust_imports']} "
        f"import_resolutions={records['rust_import_resolutions']} "
        f"references={records['rust_references']} "
        f"dependencies={records['rust_dependencies']}"
    )
    print(
        "compat handles: "
        f"files={compat_handles['files']} "
        f"symbols={compat_handles['symbols']} "
        f"interfaces={compat_handles['interfaces']} "
        f"types={compat_handles['types']} "
        f"imports={compat_handles['imports']}"
    )


def main() -> int:
    args = parse_args()
    report = make_report(Path(args.repo).expanduser().resolve(), language=args.language)
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
