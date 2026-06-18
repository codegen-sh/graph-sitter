# Phase 0 Benchmarking And Profiling

This document captures the first practical baseline plan for the Python backend before replacing the eager Python object graph with a Rust engine.

## Goals

- Measure cold `Codebase(...)` construction wall time and RSS for the current Python backend.
- Split the build into coarse phases that match today's implementation.
- Record graph size and Python object counts so memory regressions can be compared against graph scale.
- Keep the smoke benchmark runnable without a large external repository.

## Current Build Phase Map

The eager path is:

1. `Codebase.__init__` validates inputs, builds `ProjectConfig`, and constructs `CodebaseContext`.
2. `CodebaseContext.__init__` creates `rustworkx.PyDiGraph`, indexes, parser, config parser, dependency manager, and language engine.
3. `CodebaseContext.build_graph` enumerates files with `RepoOperator.iter_files`.
4. `_process_diff_files` adds files:
   - dependency manager / language engine startup if configured
   - file existence checks for incremental runs
   - new file parsing through `SourceFile.from_content`
   - tree-sitter parse through `parse_file`
   - eager Python object materialization through `SourceFile.parse`
5. `_process_diff_files` builds the directory tree with `build_directory_tree`.
6. TypeScript only: `config_parser.parse_configs` assigns nearest `tsconfig.json` data.
7. Unless `CodebaseConfig(disable_graph=True)` is set, graph resolution runs:
   - import resolution through `Import.add_symbol_resolution_edge`
   - TypeScript export dependency resolution through `TSExport.compute_export_dependencies`
   - superclass/interface dependency resolution through `compute_superclass_dependencies`
   - fixed-point dependency recompute through `_compute_dependencies` and `Importable.recompute`

The known memory-heavy points are `SourceFile._nodes`, every `Editable` retaining `ts_node`, `ctx`, `parent`, and IDs, and `CodebaseContext._graph` storing Python payload objects plus `Edge` objects.

## Harness

`rust-rewrite/tools/measure_python_backend.py` is a standalone measurement harness. It runtime-wraps stable Python backend choke points and writes a JSON report.

Smoke test with a generated tiny Python git repo:

```bash
uv run python rust-rewrite/tools/measure_python_backend.py --language python --json
```

Measure a real repo:

```bash
uv run python rust-rewrite/tools/measure_python_backend.py /path/to/repo --language python --output /tmp/python-backend-baseline.json
```

Run multiple cold samples as separate processes:

```bash
for i in 1 2 3 4 5; do
  uv run python rust-rewrite/tools/measure_python_backend.py /path/to/repo --language python \
    --output "/tmp/python-backend-baseline-$i.json"
done
```

Isolate parse/object materialization from graph resolution:

```bash
uv run python rust-rewrite/tools/measure_python_backend.py /path/to/repo --language python \
  --disable-graph --output /tmp/python-backend-parse-only.json
```

## Metrics

The JSON report includes:

- total constructor wall time
- process RSS before and after construction
- sampled process RSS peak for the full run
- `ru_maxrss` for process max RSS
- inclusive wall time and sampled RSS peak for each wrapped phase
- phase call counts and phase-specific counters, such as parsed bytes
- graph node and edge counts
- graph node counts by `NodeType`
- sum of per-file `_nodes` lengths
- optional `gc` object counts for `graph_sitter.*` classes

Phase timings are inclusive and do not sum to total time because some wrappers are nested. RSS phase attribution uses a background sampler and should be treated as trend data, not allocator-accurate attribution.

## Recommended Baseline Matrix

Use pinned commits and record hardware, Python version, OS, and command line from the JSON metadata.

| Tier | Repo | Purpose | Minimum samples |
| --- | --- | --- | --- |
| Smoke | generated fixture | CI/local sanity check | 1 |
| Small | this repo or a compact fixture repo | stable regression signal | 5 |
| Medium | representative Python service or TS package | phase distribution | 5 |
| Huge | known memory-stressing monorepo | Rust rewrite target | 3 |

For each real repo, capture both default graph mode and `--disable-graph` parse-only mode. The delta approximates resolution/dependency graph cost.

## Open Questions

- Which exact small, medium, and huge repositories should become canonical Phase 0 baselines?
- Should TypeScript baselines run with dependency manager and language engine flags off, on, or both?
- Do we need allocator-level attribution with `memray`, `tracemalloc`, or `py-spy` in addition to RSS sampling?
- What commit, dependency lockfile, and Python minor version should define the official baseline?
- Which memory target should be set for the first Rust vertical slice: total RSS, graph-only delta, or parse-only delta?
