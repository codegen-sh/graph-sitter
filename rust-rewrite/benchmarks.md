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

`rust-rewrite/tools/compare_rust_python_index.py` compares that current Python backend path with the Rust compact Python indexer. It builds the Rust release example once, generates or accepts a repo, and samples the Rust indexer process RSS.

Generated fixture comparison:

```bash
uv run python rust-rewrite/tools/compare_rust_python_index.py \
  --fixture-files 150 --fixture-functions 20 \
  --output /tmp/graph-sitter-rust-compare.json
```

Current repo comparison:

```bash
uv run python rust-rewrite/tools/compare_rust_python_index.py . \
  --output /tmp/graph-sitter-rust-compare-repo.json
```

Compare against the current full Python graph instead of parse/object materialization only:

```bash
uv run python rust-rewrite/tools/compare_rust_python_index.py . \
  --python-full-graph \
  --output /tmp/graph-sitter-rust-compare-repo-full.json
```

`rust-rewrite/tools/measure_rust_facade.py` measures the Python-facing Rust compact-index facade. It expects the PyO3 extension module to be importable as `graph_sitter_py`. By default it discovers files through the same Python `RepoOperator.iter_files(...)` filters used by `CodebaseContext`, then passes that selected list into Rust:

```bash
PYTHONPATH=/path/to/dir/containing/graph_sitter_py_extension \
  uv run python rust-rewrite/tools/measure_rust_facade.py . --json
```

Use `--raw-rust-walk` to measure Rust's standalone recursive walk instead of Python-selected file discovery.

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

## Initial Rust Index Evidence

These measurements are for the first Rust vertical slice only: repo walk, tree-sitter Python parsing, top-level class/function extraction, and import extraction into compact Rust records. This is not yet full `Codebase` API parity and does not yet include dependency graph resolution.

Commands were run on this branch on 2026-06-18.

| Input | Python mode | Python wall | Python max RSS | Rust index wall | Rust process wall | Rust sampled RSS | Wall ratio | RSS ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Generated fixture, 150 modules x 20 helpers | `--disable-graph` | 0.460s | 166.3 MB | 0.047s | 0.281s | 3.3 MB | 9.875x | 50.918x |
| Generated fixture, 150 modules x 20 helpers | full graph | 1.147s | 208.5 MB | 0.038s | 0.051s | 3.1 MB | 30.502x | 66.380x |
| `graph-sitter` repo checkout | `--disable-graph` | 2.874s | 531.9 MB | 0.317s | 0.333s | 7.6 MB | 9.069x | 70.045x |
| `graph-sitter` repo checkout | full graph | 7.448s | 788.8 MB | 0.331s | 0.342s | 7.6 MB | 22.480x | 103.877x |

The most conservative current-repo comparison is parse/object materialization only: Rust is about 9x faster and about 70x lower RSS for the implemented compact-index slice. Against today's full graph construction on this repo, Rust is about 22x faster and about 104x lower RSS for the same implemented slice.

## Python-Facing Rust Facade Evidence

These measurements use the new Python shell integration path: Python discovers files with `RepoOperator.iter_files(...)`, the selected file list is passed to the PyO3 extension, and Rust builds the compact index. This includes Python interpreter/import overhead and is therefore a higher RSS number than the standalone Rust process, but it is the relevant measurement for an opt-in Python shell path.

Commands were run on this branch on 2026-06-18 after adding selected-file PyO3 indexing.

| Input | Python mode | Python wall | Python max RSS | Rust facade wall | Rust facade max RSS | Python files | Rust selected files | Rust import resolutions | Wall ratio | RSS ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `graph-sitter` repo checkout | `--disable-graph` | 2.938s | 533.3 MB | 0.687s | 116.5 MB | 1129 | 1129 | 432 | 4.277x | 4.579x |

This shell-facing number is intentionally more conservative than the standalone Rust process benchmark because it includes Python startup, imports, and repo file discovery. The important result is that the selected-file integration preserves Python file-discovery parity for the current repo while still cutting parse/index/import-resolution wall time and process max RSS substantially for the implemented compact graph slice.

Important caveats:

- The Rust indexer currently extracts a compact subset: files, top-level Python classes/functions, imports, and internal import-resolution records for indexed Python modules.
- The Python-facing Rust facade uses Python's selected file list, but the compact Rust records are not yet full Python graph parity. Symbol and import totals should not be compared directly with current Python graph node totals until the resolver and lazy handle layers are implemented.
- The Python backend numbers include the current eager Python object materialization and, in full graph mode, dependency edge computation.
- The Rust RSS number is sampled from a short-lived release process; it is suitable for directional comparison, not allocator-level attribution.
- The generated fixture and this repo are useful proof points, but the huge-repo target still needs canonical pinned baselines.

## Open Questions

- Which exact small, medium, and huge repositories should become canonical Phase 0 baselines?
- Should TypeScript baselines run with dependency manager and language engine flags off, on, or both?
- Do we need allocator-level attribution with `memray`, `tracemalloc`, or `py-spy` in addition to RSS sampling?
- What commit, dependency lockfile, and Python minor version should define the official baseline?
- Which memory target should be set for the first Rust vertical slice: total RSS, graph-only delta, or parse-only delta?
