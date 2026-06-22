"""Generate a module-level dependency graph for the Next.js framework core.

Parses packages/next/src with the graph-sitter Rust backend and emits a JSON
graph (modules as nodes, aggregated import edges) for the docs visualization.

Run from the repo root:
    uv run python site/scripts/gen-nextjs-depgraph.py
"""
import json
import os
import time
from collections import defaultdict
from pathlib import Path

REPO = os.environ.get("NEXTJS_REPO", "/Users/jayhack/.codex/worktrees/0554/nextjs-sample")
SUBDIR = "packages/next/src/"
PREFIX = "packages/next/src/"
OUT = Path(__file__).resolve().parents[1] / "lib" / "data" / "nextjs-depgraph.json"

from graph_sitter.codebase.config import ProjectConfig
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode
from graph_sitter.core.codebase import Codebase


def module_of(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) <= 1:
        return "(root)"
    if len(parts) == 2:
        return parts[0]
    return f"{parts[0]}/{parts[1]}"


def group_of(rel: str) -> str:
    return rel.split("/")[0] if "/" in rel else "(root)"


def main() -> None:
    project = ProjectConfig.from_path(REPO).model_copy(update={"subdirectories": [SUBDIR]})
    t0 = time.perf_counter()
    cb = Codebase(
        projects=[project],
        config=CodebaseConfig(graph_backend=GraphBackend("rust"), rust_fallback=RustFallbackMode("error")),
    )
    elapsed = time.perf_counter() - t0

    files = {f.id: f for f in cb.rust_files}

    def rel_of(fid: int):
        p = files[fid].path if fid in files else None
        if not p or not p.startswith(PREFIX):
            return None
        return p[len(PREFIX):]

    # Aggregate file metrics into modules
    mod_files = defaultdict(int)
    mod_loc = defaultdict(int)
    mod_symbols = defaultdict(int)
    mod_group = {}
    file_module = {}
    for fid, f in files.items():
        rel = rel_of(fid)
        if rel is None:
            continue
        m = module_of(rel)
        file_module[fid] = m
        mod_files[m] += 1
        mod_loc[m] += f.line_count or 0
        mod_group[m] = group_of(rel)

    for s in cb.rust_symbols:
        m = file_module.get(s.file_id)
        if m is not None:
            mod_symbols[m] += 1

    # Aggregate module->module import edges from file-level import resolutions
    edge_w = defaultdict(int)
    for r in cb.rust_import_resolutions:
        sm = file_module.get(r.source_file_id)
        tm = file_module.get(r.target_file_id)
        if sm is None or tm is None or sm == tm:
            continue
        edge_w[(sm, tm)] += 1

    inbound = defaultdict(int)
    outbound = defaultdict(int)
    for (sm, tm), w in edge_w.items():
        inbound[tm] += w
        outbound[sm] += w

    nodes = []
    for m in sorted(mod_files):
        nodes.append(
            {
                "id": m,
                "group": mod_group.get(m, "(root)"),
                "files": mod_files[m],
                "loc": mod_loc[m],
                "symbols": mod_symbols[m],
                "inbound": inbound.get(m, 0),
                "outbound": outbound.get(m, 0),
            }
        )

    edges = [
        {"source": sm, "target": tm, "weight": w}
        for (sm, tm), w in sorted(edge_w.items(), key=lambda kv: -kv[1])
    ]

    groups = sorted({n["group"] for n in nodes})

    payload = {
        "meta": {
            "source": "vercel/next.js · packages/next/src",
            "parser": "graph-sitter (rust backend)",
            "parse_seconds": round(elapsed, 2),
            "files": sum(mod_files.values()),
            "modules": len(nodes),
            "edges": len(edges),
            "symbols": len(list(cb.rust_symbols)),
        },
        "groups": groups,
        "nodes": nodes,
        "edges": edges,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"parsed in {elapsed:.2f}s")
    print(f"modules={len(nodes)} edges={len(edges)} groups={groups}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
