#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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


def current_rss_bytes() -> int:
    import psutil

    return int(psutil.Process(os.getpid()).memory_info().rss)


def memory_sample(label: str) -> dict[str, float | str]:
    return {
        "label": label,
        "rss_mb": round(bytes_to_mb(current_rss_bytes()), 3),
        "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
    }


def make_report(repo: Path, *, language: str) -> dict:
    memory_samples = [memory_sample("start")]
    config = CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)
    start = time.perf_counter()
    codebase = Codebase(str(repo), language=language, config=config)
    wall = time.perf_counter() - start
    memory_samples.append(memory_sample("after_codebase_construct"))
    python_graph_blocked = False
    try:
        len(codebase.ctx.nodes)
    except RuntimeError:
        python_graph_blocked = True
    memory_samples.append(memory_sample("after_python_graph_block_check"))

    backend = codebase.ctx.rust_index
    assert backend is not None
    summary = codebase.rust_index_summary
    summary_counts = {
        "files": summary.files,
        "symbols": summary.symbols,
        "classes": summary.classes,
        "functions": summary.functions,
        "global_variables": summary.global_variables,
        "imports": summary.imports,
        "import_resolutions": summary.import_resolutions,
        "external_modules": summary.external_modules,
        "references": summary.references,
        "external_references": summary.external_references,
        "dependencies": summary.dependencies,
        "exports": summary.exports,
        "subclass_edges": summary.subclass_edges,
        "bytes": summary.bytes,
        "lines": summary.lines,
        "files_with_errors": summary.files_with_errors,
    }
    memory_samples.append(memory_sample("after_summary_counts"))
    records = backend.compact_record_counts()
    memory_samples.append(memory_sample("after_record_counts"))
    compat_handles = backend.compact_compat_counts()
    memory_samples.append(memory_sample("after_compat_handles"))
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
            "current_rss_mb": memory_samples[-1]["rss_mb"],
        },
        "rss_samples": memory_samples,
        "summary": summary_counts,
        "records": records,
        "compat_handles": compat_handles,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure Codebase construction with the opt-in compact Rust backend.")
    parser.add_argument("repo", nargs="?", default=".", help="Path to the repository to index.")
    parser.add_argument("--language", choices=["python", "typescript"], default="python", help="Codebase language to index.")
    parser.add_argument("--extension-dir", type=Path, help="Optional directory containing a built graph_sitter_py extension module.")
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
    print(
        f"rust Codebase: wall={totals['wall_seconds']:.3f}s "
        f"max_rss={totals['max_rss_mb']:.1f} MB current_rss={totals['current_rss_mb']:.1f} MB"
    )
    print(f"python graph blocked: {report['metadata']['python_graph_blocked']}")
    print(
        "rss samples: "
        + " -> ".join(f"{sample['label']}={sample['rss_mb']:.1f} MB" for sample in report["rss_samples"])
    )
    print(
        "summary: "
        f"files={summary['files']} "
        f"symbols={summary['symbols']} "
        f"global_variables={summary['global_variables']} "
        f"imports={summary['imports']} "
        f"import_resolutions={summary['import_resolutions']} "
        f"external_modules={summary['external_modules']} "
        f"external_references={summary.get('external_references', 0)} "
        f"references={summary['references']} "
        f"dependencies={summary['dependencies']}"
    )
    print(
        "records: "
        f"files={records['rust_files']} "
        f"symbols={records['rust_symbols']} "
        f"imports={records['rust_imports']} "
        f"import_resolutions={records['rust_import_resolutions']} "
        f"external_modules={records['rust_external_modules']} "
        f"exports={records['rust_exports']} "
        f"references={records['rust_references']} "
        f"external_references={records.get('rust_external_references', 0)} "
        f"dependencies={records['rust_dependencies']}"
    )
    print(
        "compat handles: "
        f"files={compat_handles['files']} "
        f"symbols={compat_handles['symbols']} "
        f"interfaces={compat_handles['interfaces']} "
        f"types={compat_handles['types']} "
        f"imports={compat_handles['imports']} "
        f"external_modules={compat_handles['external_modules']} "
        f"exports={compat_handles['exports']}"
    )


def main() -> int:
    args = parse_args()
    if args.extension_dir is not None:
        sys.path.insert(0, str(args.extension_dir.resolve()))
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
