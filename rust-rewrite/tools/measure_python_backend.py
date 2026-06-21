#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def bytes_to_mb(value: float) -> float:
    return value / (1024 * 1024)


def current_rss_bytes() -> int:
    import psutil

    return int(psutil.Process(os.getpid()).memory_info().rss)


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss * 1024)


@dataclass
class PhaseStats:
    calls: int = 0
    wall_seconds: float = 0.0
    rss_peak_bytes: int = 0
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))


class Recorder:
    def __init__(self, sample_interval: float) -> None:
        self.sample_interval = sample_interval
        self._lock = threading.Lock()
        self._stack: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.phases: dict[str, PhaseStats] = defaultdict(PhaseStats)
        self.rss_peak_bytes = 0

    @contextmanager
    def measure(self, phase: str):
        with self._lock:
            self._stack.append(phase)
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            rss = current_rss_bytes()
            with self._lock:
                if self._stack and self._stack[-1] == phase:
                    self._stack.pop()
                elif phase in self._stack:
                    self._stack.remove(phase)
                stats = self.phases[phase]
                stats.calls += 1
                stats.wall_seconds += elapsed
                stats.rss_peak_bytes = max(stats.rss_peak_bytes, rss)
                self.rss_peak_bytes = max(self.rss_peak_bytes, rss)

    def add_counter(self, phase: str, key: str, value: int) -> None:
        with self._lock:
            self.phases[phase].counters[key] += int(value)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._sample_loop, name="rss-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.sample_interval * 4))
        self._sample_once()

    def _sample_loop(self) -> None:
        while not self._stop.wait(self.sample_interval):
            self._sample_once()

    def _sample_once(self) -> None:
        rss = current_rss_bytes()
        with self._lock:
            self.rss_peak_bytes = max(self.rss_peak_bytes, rss)
            if self._stack:
                phase = self._stack[-1]
                self.phases[phase].rss_peak_bytes = max(self.phases[phase].rss_peak_bytes, rss)

    def as_jsonable(self) -> list[dict[str, Any]]:
        rows = []
        for name, stats in sorted(self.phases.items()):
            rows.append(
                {
                    "name": name,
                    "calls": stats.calls,
                    "wall_seconds": round(stats.wall_seconds, 6),
                    "rss_peak_mb": round(bytes_to_mb(stats.rss_peak_bytes), 3),
                    "counters": dict(sorted(stats.counters.items())),
                }
            )
        return rows


def patch_method(
    recorder: Recorder,
    patches: list[tuple[Any, str, Any]],
    owner: Any,
    method_name: str,
    phase: str,
) -> None:
    original = getattr(owner, method_name)

    @wraps(original)
    def wrapped(*args, **kwargs):
        with recorder.measure(phase):
            return original(*args, **kwargs)

    setattr(owner, method_name, wrapped)
    patches.append((owner, method_name, original))


def patch_iter_files(recorder: Recorder, patches: list[tuple[Any, str, Any]], repo_operator_cls: Any) -> None:
    original = repo_operator_cls.iter_files

    @wraps(original)
    def wrapped(self, *args, **kwargs):
        iterator = original(self, *args, **kwargs)

        def measured_iterator():
            yielded = 0
            while True:
                try:
                    with recorder.measure("repo_iter_files"):
                        item = next(iterator)
                except StopIteration:
                    break
                yielded += 1
                yield item
            recorder.add_counter("repo_iter_files", "items_yielded", yielded)

        return measured_iterator()

    repo_operator_cls.iter_files = wrapped
    patches.append((repo_operator_cls, "iter_files", original))


def install_instrumentation(recorder: Recorder) -> list[tuple[Any, str, Any]]:
    import graph_sitter.core.file as file_module
    import graph_sitter.tree_sitter_parser as parser_module
    from graph_sitter.codebase.codebase_context import CodebaseContext
    from graph_sitter.core.class_definition import Class
    from graph_sitter.core.file import SourceFile
    from graph_sitter.core.import_resolution import Import
    from graph_sitter.core.interface import Interface
    from graph_sitter.core.interfaces.importable import Importable
    from graph_sitter.core.symbol_groups.parents import Parents
    from graph_sitter.git.repo_operator.repo_operator import RepoOperator
    from graph_sitter.typescript.config_parser import TSConfigParser
    from graph_sitter.typescript.export import TSExport

    patches: list[tuple[Any, str, Any]] = []

    original_parse_file = file_module.parse_file

    @wraps(original_parse_file)
    def parse_file_wrapper(filepath, content):
        if isinstance(content, str):
            recorder.add_counter("tree_sitter_parse_file", "bytes", len(content.encode("utf-8")))
        with recorder.measure("tree_sitter_parse_file"):
            return original_parse_file(filepath, content)

    file_module.parse_file = parse_file_wrapper
    patches.append((file_module, "parse_file", original_parse_file))
    if parser_module.parse_file is original_parse_file:
        parser_module.parse_file = parse_file_wrapper
        patches.append((parser_module, "parse_file", original_parse_file))

    patch_iter_files(recorder, patches, RepoOperator)
    patch_method(recorder, patches, CodebaseContext, "build_graph", "build_graph_total")
    patch_method(recorder, patches, CodebaseContext, "_process_diff_files", "process_diff_files_total")
    patch_method(recorder, patches, CodebaseContext, "build_directory_tree", "directory_tree")
    patch_method(recorder, patches, CodebaseContext, "_compute_dependencies", "dependency_fixed_point")
    patch_method(recorder, patches, SourceFile, "parse", "sourcefile_object_parse")
    patch_method(recorder, patches, Import, "add_symbol_resolution_edge", "import_resolution")
    patch_method(recorder, patches, Importable, "recompute", "importable_recompute")
    patch_method(recorder, patches, TSConfigParser, "parse_configs", "config_parse")
    patch_method(recorder, patches, TSExport, "compute_export_dependencies", "export_resolution")
    patch_method(recorder, patches, Class, "compute_superclass_dependencies", "superclass_resolution")
    patch_method(recorder, patches, Interface, "compute_superclass_dependencies", "superclass_resolution")
    patch_method(recorder, patches, Parents, "compute_superclass_dependencies", "superclass_resolution")

    return patches


def restore_patches(patches: list[tuple[Any, str, Any]]) -> None:
    for owner, method_name, original in reversed(patches):
        setattr(owner, method_name, original)


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_python_fixture(base_dir: Path, file_count: int, functions_per_file: int) -> Path:
    repo_path = base_dir / "python-smoke-repo"
    package = repo_path / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .module_0 import Class0\n", encoding="utf-8")
    for idx in range(file_count):
        previous_import = "" if idx == 0 else f"from .module_{idx - 1} import Class{idx - 1}, helper_{idx - 1}_0\n"
        functions = "\n\n".join([f"def helper_{idx}_{fn}(value: int) -> int:\n    total = value + {idx} + {fn}\n    return total\n" for fn in range(functions_per_file)])
        parent = f"Class{idx - 1}" if idx else "object"
        inherited_call = f"helper_{idx - 1}_0(value)" if idx else "value"
        content = (
            "from __future__ import annotations\n"
            f"{previous_import}\n\n"
            f"class Class{idx}({parent}):\n"
            "    def __init__(self, value: int) -> None:\n"
            f"        self.value = {inherited_call}\n\n"
            "    def compute(self) -> int:\n"
            f"        return helper_{idx}_0(self.value)\n\n"
            f"{functions}\n"
        )
        (package / f"module_{idx}.py").write_text(content, encoding="utf-8")
    run_git(repo_path, "init")
    run_git(repo_path, "add", ".")
    return repo_path


def summarize_graph(codebase: Any) -> dict[str, Any]:
    from graph_sitter.core.file import SourceFile

    ctx = codebase.ctx
    nodes = list(ctx.nodes)
    edges = list(ctx.edges)
    node_types = Counter(getattr(node.node_type, "name", str(node.node_type)) for node in nodes)
    files = [node for node in nodes if isinstance(node, SourceFile)]
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "node_types": dict(sorted(node_types.items())),
        "source_files": len(files),
        "source_file_nodes_total": sum(len(getattr(file, "_nodes", [])) for file in files),
        "directories": len(getattr(ctx, "directories", {})),
    }


def summarize_objects(skip: bool) -> dict[str, Any] | None:
    if skip:
        return None
    gc.collect()
    counts: Counter[str] = Counter()
    total = 0
    for obj in gc.get_objects():
        cls = type(obj)
        module = getattr(cls, "__module__", "")
        if not isinstance(module, str):
            continue
        if module.startswith("graph_sitter"):
            total += 1
            counts[f"{module}.{cls.__qualname__}"] += 1
    return {
        "graph_sitter_objects": total,
        "top_classes": counts.most_common(30),
    }


def build_codebase(args: argparse.Namespace) -> tuple[Any, Path, bool, tempfile.TemporaryDirectory[str] | None]:
    from graph_sitter.configs.models.codebase import CodebaseConfig
    from graph_sitter.core.codebase import Codebase

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    generated_fixture = False
    if args.repo is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="graph-sitter-bench-")
        repo_path = create_python_fixture(Path(temp_dir.name), args.fixture_files, args.fixture_functions)
        generated_fixture = True
    else:
        repo_path = Path(args.repo).expanduser().resolve()

    config = CodebaseConfig(disable_graph=args.disable_graph)
    language = None if args.language == "auto" else args.language
    codebase = Codebase(str(repo_path), language=language, config=config)
    return codebase, repo_path, generated_fixture, temp_dir


def make_report(args: argparse.Namespace) -> dict[str, Any]:
    recorder = Recorder(sample_interval=args.sample_interval)
    patches = install_instrumentation(recorder)
    rss_start = current_rss_bytes()
    start = time.perf_counter()
    recorder.start()
    temp_dir = None
    try:
        with recorder.measure("codebase_construct"):
            codebase, repo_path, generated_fixture, temp_dir = build_codebase(args)
    finally:
        recorder.stop()
        restore_patches(patches)
    wall = time.perf_counter() - start
    rss_end = current_rss_bytes()

    report = {
        "metadata": {
            "repo_path": str(repo_path),
            "generated_fixture": generated_fixture,
            "language": args.language,
            "disable_graph": args.disable_graph,
            "python": sys.version,
            "platform": platform.platform(),
            "sample_interval_seconds": args.sample_interval,
            "command": " ".join(sys.argv),
        },
        "totals": {
            "wall_seconds": round(wall, 6),
            "rss_start_mb": round(bytes_to_mb(rss_start), 3),
            "rss_end_mb": round(bytes_to_mb(rss_end), 3),
            "rss_peak_sampled_mb": round(bytes_to_mb(recorder.rss_peak_bytes), 3),
            "max_rss_mb": round(bytes_to_mb(max_rss_bytes()), 3),
        },
        "phases": recorder.as_jsonable(),
        "graph": summarize_graph(codebase),
        "objects": summarize_objects(args.skip_object_counts),
    }
    if temp_dir is not None:
        temp_dir.cleanup()
    return report


def print_human(report: dict[str, Any]) -> None:
    totals = report["totals"]
    graph = report["graph"]
    print(f"repo: {report['metadata']['repo_path']}")
    print(f"wall: {totals['wall_seconds']:.3f}s")
    print(f"rss: start={totals['rss_start_mb']:.1f} MB end={totals['rss_end_mb']:.1f} MB peak={totals['rss_peak_sampled_mb']:.1f} MB max={totals['max_rss_mb']:.1f} MB")
    print(f"graph: nodes={graph['nodes']} edges={graph['edges']} files={graph['source_files']} file_nodes={graph['source_file_nodes_total']}")
    print("phases:")
    for phase in report["phases"]:
        print(f"  {phase['name']}: calls={phase['calls']} wall={phase['wall_seconds']:.3f}s rss_peak={phase['rss_peak_mb']:.1f} MB")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure current graph-sitter Python backend cold parse RSS and wall time.")
    parser.add_argument("repo", nargs="?", help="Path to a git repository. If omitted, a tiny Python fixture repo is generated.")
    parser.add_argument("--language", choices=["auto", "python", "typescript"], default="auto", help="Language passed to Codebase.")
    parser.add_argument("--disable-graph", action="store_true", help="Set CodebaseConfig(disable_graph=True) to isolate parse/object materialization.")
    parser.add_argument("--fixture-files", type=int, default=8, help="Generated fixture Python module count when repo is omitted.")
    parser.add_argument("--fixture-functions", type=int, default=8, help="Generated helper functions per fixture module when repo is omitted.")
    parser.add_argument("--sample-interval", type=float, default=0.01, help="RSS sampling interval in seconds.")
    parser.add_argument("--skip-object-counts", action="store_true", help="Skip post-run gc object counting.")
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
