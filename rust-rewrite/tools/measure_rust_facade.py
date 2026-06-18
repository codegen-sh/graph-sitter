#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
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

from graph_sitter.codebase.codebase_context import GLOBAL_FILE_IGNORE_LIST, get_node_classes  # noqa: E402
from graph_sitter.codebase.config import ProjectConfig  # noqa: E402
from graph_sitter.codebase.rust_backend import RustIndexBackend  # noqa: E402
from graph_sitter.shared.enums.programming_language import ProgrammingLanguage  # noqa: E402


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


def discover_python_files(repo: Path) -> tuple[Path, list[str]]:
    project = ProjectConfig.from_path(str(repo), programming_language=ProgrammingLanguage.PYTHON)
    node_classes = get_node_classes(ProgrammingLanguage.PYTHON)
    extensions = node_classes.file_cls.get_extensions()
    file_paths = [
        str(filepath)
        for filepath, _ in project.repo_operator.iter_files(
            subdirs=project.subdirectories,
            extensions=extensions,
            ignore_list=GLOBAL_FILE_IGNORE_LIST,
        )
    ]
    return Path(project.repo_operator.repo_path).resolve(), file_paths


def make_report(repo: Path, *, raw_rust_walk: bool) -> dict:
    start = time.perf_counter()
    if raw_rust_walk:
        repo_root = repo
        file_paths = None
    else:
        repo_root, file_paths = discover_python_files(repo)
    backend = RustIndexBackend.build(repo_root, file_paths=file_paths)
    wall = time.perf_counter() - start
    return {
        "metadata": {
            "repo_path": str(repo),
            "repo_root": str(repo_root),
            "raw_rust_walk": raw_rust_walk,
            "selected_file_count": None if file_paths is None else len(file_paths),
            "python": sys.version,
            "platform": platform.platform(),
            "engine_version": backend.engine_version,
        },
        "totals": {
            "wall_seconds": round(wall, 6),
            "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
        },
        "summary": dataclasses.asdict(backend.summary),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure the Python-facing Rust compact index facade.")
    parser.add_argument("repo", nargs="?", default=".", help="Path to the Python repository to index.")
    parser.add_argument("--raw-rust-walk", action="store_true", help="Use Rust's recursive file walk instead of Python RepoOperator file discovery.")
    parser.add_argument("--output", type=Path, help="Optional path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a human summary.")
    return parser.parse_args()


def print_human(report: dict) -> None:
    totals = report["totals"]
    summary = report["summary"]
    print(f"repo: {report['metadata']['repo_path']}")
    print(f"repo root: {report['metadata']['repo_root']}")
    print(f"engine: {report['metadata']['engine_version']}")
    print(f"raw rust walk: {report['metadata']['raw_rust_walk']}")
    print(f"selected files: {report['metadata']['selected_file_count']}")
    print(f"rust facade: wall={totals['wall_seconds']:.3f}s max_rss={totals['max_rss_mb']:.1f} MB")
    print(f"summary: files={summary['files']} symbols={summary['symbols']} imports={summary['imports']}")


def main() -> int:
    args = parse_args()
    report = make_report(Path(args.repo).expanduser().resolve(), raw_rust_walk=args.raw_rust_walk)
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
