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
1. `CodebaseContext.__init__` creates `rustworkx.PyDiGraph`, indexes, parser, config parser, dependency manager, and language engine.
1. `CodebaseContext.build_graph` enumerates files with `RepoOperator.iter_files`.
1. `_process_diff_files` adds files:
   - dependency manager / language engine startup if configured
   - file existence checks for incremental runs
   - new file parsing through `SourceFile.from_content`
   - tree-sitter parse through `parse_file`
   - eager Python object materialization through `SourceFile.parse`
1. `_process_diff_files` builds the directory tree with `build_directory_tree`.
1. TypeScript only: `config_parser.parse_configs` assigns nearest `tsconfig.json` data.
1. Unless `CodebaseConfig(disable_graph=True)` is set, graph resolution runs:
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

`rust-rewrite/tools/measure_codebase_rust_backend.py` measures actual `Codebase(...)` construction with `CodebaseConfig(graph_backend="rust", rust_fallback="error")`. It verifies that the lazy Python graph is blocked and reports compact Rust record counts:

```bash
PYTHONPATH=/path/to/dir/containing/graph_sitter_py_extension \
  uv run python rust-rewrite/tools/measure_codebase_rust_backend.py . --json
```

Pass `--language typescript` to measure the compact Rust TypeScript/JavaScript Codebase shell instead of the Python shell:

```bash
PYTHONPATH=/path/to/dir/containing/graph_sitter_py_extension \
  uv run python rust-rewrite/tools/measure_codebase_rust_backend.py /path/to/ts-repo --language typescript --json
```

`rust-rewrite/tools/benchmark_pinned_python_repo.py` prepares a pinned external Python repository, builds the PyO3 extension, runs the Python parse/object-materialization harness, runs the Rust compact `Codebase` harness, and fails if the configured wall/RSS ratio gates are not met. The default pinned repo is Apache Airflow `2.10.5`, resolved to commit `b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`:

```bash
uv run python rust-rewrite/tools/benchmark_pinned_python_repo.py \
  --output /tmp/graph-sitter-airflow-2.10.5-benchmark.json \
  --json
```

`rust-rewrite/tools/measure_typescript_rust_index.py` measures the standalone compact Rust TypeScript/JavaScript syntax index through the PyO3 extension. By default it discovers `.js`, `.jsx`, `.ts`, and `.tsx` files through the same Python `RepoOperator.iter_files(...)` filters used by `CodebaseContext`, then passes that selected list into Rust:

```bash
PYTHONPATH=/path/to/dir/containing/graph_sitter_py_extension \
  uv run python rust-rewrite/tools/measure_typescript_rust_index.py /path/to/ts-repo --json
```

Use `--raw-rust-walk` to measure Rust's standalone recursive TS/JS walk instead of Python-selected file discovery.

`rust-rewrite/tools/benchmark_pinned_typescript_repo.py` prepares a pinned external TypeScript/JavaScript repository, builds the PyO3 extension, runs the Python TS parse/object-materialization harness, runs the Rust TS syntax-index harness, and fails if the configured wall/RSS ratio gates are not met. The default pinned repo is Next.js `v15.0.0`, resolved to commit `51bfe3c1863b191f4b039bc230e8ed5c57b0baf3`:

```bash
uv run python rust-rewrite/tools/benchmark_pinned_typescript_repo.py \
  --output /tmp/graph-sitter-nextjs-v15.0.0-benchmark.json \
  --json
```

`rust-rewrite/tools/snapshot_pinned_python_repo.py` verifies a deterministic compact Rust graph snapshot for the same pinned Airflow checkout. The committed golden stores counts, stable SHA-256 digests, and sorted sample rows for files, symbols, imports, import resolutions, references, and dependencies:

```bash
uv run python rust-rewrite/tools/snapshot_pinned_python_repo.py
```

Refresh the committed snapshot after intentional compact-IR changes:

```bash
uv run python rust-rewrite/tools/snapshot_pinned_python_repo.py --update
```

The same check is available as an opt-in pytest integration test:

```bash
GRAPH_SITTER_RUN_PINNED_AIRFLOW_SNAPSHOT=1 \
  uv run pytest tests/integration/rust_rewrite/test_pinned_airflow_snapshot.py -q
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

| Tier   | Repo                                        | Purpose                  | Minimum samples |
| ------ | ------------------------------------------- | ------------------------ | --------------- |
| Smoke  | generated fixture                           | CI/local sanity check    | 1               |
| Small  | this repo or a compact fixture repo         | stable regression signal | 5               |
| Medium | representative Python service or TS package | phase distribution       | 5               |
| Huge   | known memory-stressing monorepo             | Rust rewrite target      | 3               |

For each real repo, capture both default graph mode and `--disable-graph` parse-only mode. The delta approximates resolution/dependency graph cost.

## Initial Rust Index Evidence

These measurements are for the first Rust vertical slice only: repo walk, tree-sitter Python parsing, top-level class/function extraction, and import extraction into compact Rust records. This is not yet full `Codebase` API parity and does not yet include dependency graph resolution.

Commands were run on this branch on 2026-06-18.

| Input                                       | Python mode       | Python wall | Python max RSS | Rust index wall | Rust process wall | Rust sampled RSS | Wall ratio | RSS ratio |
| ------------------------------------------- | ----------------- | ----------: | -------------: | --------------: | ----------------: | ---------------: | ---------: | --------: |
| Generated fixture, 150 modules x 20 helpers | `--disable-graph` |      0.460s |       166.3 MB |          0.047s |            0.281s |           3.3 MB |     9.875x |   50.918x |
| Generated fixture, 150 modules x 20 helpers | full graph        |      1.147s |       208.5 MB |          0.038s |            0.051s |           3.1 MB |    30.502x |   66.380x |
| `graph-sitter` repo checkout                | `--disable-graph` |      2.874s |       531.9 MB |          0.317s |            0.333s |           7.6 MB |     9.069x |   70.045x |
| `graph-sitter` repo checkout                | full graph        |      7.448s |       788.8 MB |          0.331s |            0.342s |           7.6 MB |    22.480x |  103.877x |

The most conservative current-repo comparison is parse/object materialization only: Rust is about 9x faster and about 70x lower RSS for the implemented compact-index slice. Against today's full graph construction on this repo, Rust is about 22x faster and about 104x lower RSS for the same implemented slice.

## Python-Facing Rust Facade Evidence

These measurements use the new Python shell integration path: Python discovers files with `RepoOperator.iter_files(...)`, the selected file list is passed to the PyO3 extension, and Rust builds the compact index. This includes Python interpreter/import overhead and is therefore a higher RSS number than the standalone Rust process, but it is the relevant measurement for an opt-in Python shell path.

Commands were run on this branch on 2026-06-18 after adding selected-file PyO3 indexing.

| Input                        | Python mode       | Python wall | Python max RSS | Rust facade wall | Rust facade max RSS | Python files | Rust selected files | Rust globals | Rust import resolutions | Wall ratio | RSS ratio |
| ---------------------------- | ----------------- | ----------: | -------------: | ---------------: | ------------------: | -----------: | ------------------: | -----------: | ----------------------: | ---------: | --------: |
| `graph-sitter` repo checkout | `--disable-graph` |      2.987s |       535.0 MB |           0.692s |            115.3 MB |         1129 |                1129 |          799 |                     432 |     4.317x |    4.638x |

This shell-facing number is intentionally more conservative than the standalone Rust process benchmark because it includes Python startup, imports, and repo file discovery. The important result is that the selected-file integration preserves Python file-discovery parity for the current repo while still cutting parse/index/import-resolution wall time and process max RSS substantially for the implemented compact graph slice.

## Rust `Codebase` Construction Evidence

These measurements use real `Codebase(...)` construction with `CodebaseConfig(graph_backend="rust", rust_fallback="error")`. In this mode, once the compact Rust index builds successfully, `CodebaseContext` does not build the eager Python graph. The Rust path now exercises public Python `Codebase.files`, `symbols`, `classes`, `functions`, `global_vars`, and `imports` compatibility handles, and TypeScript file/symbol/import/export compatibility handles, while `CodebaseContext.nodes` remains blocked so the old graph cannot be materialized accidentally.

| Input                                                                | Python mode       | Python wall | Python max RSS | Rust `Codebase` wall | Rust `Codebase` max RSS | Python files | Rust files | Rust symbols | Rust imports | Rust import resolutions | Rust references | Rust dependencies | Python graph blocked | Wall ratio | RSS ratio |
| -------------------------------------------------------------------- | ----------------- | ----------: | -------------: | -------------------: | ----------------------: | -----------: | ---------: | -----------: | -----------: | ----------------------: | --------------: | ----------------: | -------------------- | ---------: | --------: |
| `graph-sitter` repo checkout                                         | `--disable-graph` |      2.731s |       543.0 MB |               0.681s |                124.0 MB |         1133 |       1133 |         6505 |         6496 |                     432 |            4110 |              2953 | yes                  |     4.009x |    4.378x |
| Apache Airflow `2.10.5` (`b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`) | `--disable-graph` |     18.940s |      3469.5 MB |               4.085s |                266.2 MB |         4789 |       4789 |        52339 |        40580 |                   19011 |          109817 |             71932 | yes                  |     4.637x |   13.031x |

### Python-Shell File Discovery Optimization

On 2026-06-20, the Rust `Codebase` setup path was changed to do a single path-only `RepoOperator.iter_files(..., skip_content=True)` walk, then filter source extensions in memory. Before this change, the Python shell asked `RepoOperator` for source files with content enabled and then walked all files again for directory/file-shell parity. Rust immediately reread the source bytes for parsing, so the first Python content read was duplicate I/O and transient allocation.

Regression coverage:

```bash
uv run pytest tests/unit/sdk/codebase/test_rust_backend.py::test_rust_compact_discovers_paths_without_python_source_reads -q
```

The test asserts that compact Rust setup makes exactly one repo-operator file walk and that the walk uses `skip_content=True`.

Measured with the same local PyO3 extension before and after the Python-shell change:

| Input                        | Before Rust `Codebase` wall | After Rust `Codebase` wall | Before max RSS | After max RSS | Wall improvement |
| ---------------------------- | --------------------------: | -------------------------: | -------------: | ------------: | ---------------: |
| `graph-sitter` repo checkout |                      0.979s |                     0.848s |       143.0 MB |      143.2 MB |            1.16x |

Discovery-only old-vs-new measurements were run in the same process to isolate the removed work:

| Input                                                                | Old source scan with content | Old all-file path scan | Old total | New single path scan | New extension filter | New total | File sets match |
| -------------------------------------------------------------------- | ---------------------------: | ---------------------: | --------: | -------------------: | -------------------: | --------: | --------------- |
| `graph-sitter` repo checkout                                         |                       0.112s |                 0.055s |    0.167s |               0.059s |               0.000s |    0.059s | yes             |
| Apache Airflow `2.10.5` (`b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`) |                       0.684s |                 0.162s |    0.846s |               0.143s |               0.001s |    0.144s | yes             |

The Airflow discovery slice is now about 5.9x faster before Rust parsing begins, while selecting the same 4,789 Python source files and 7,765 total repo files.

### Top-Level Symbol Query Optimization

On 2026-06-20, the Rust PyO3 extension added top-level symbol-list methods so common public `Codebase` queries no longer deserialize every compact symbol into Python handles. Before this change, `codebase.functions`, `codebase.classes`, and similar top-level lists routed through `RustIndexBackend.symbol_handles`, materializing all compact symbols even when the caller only needed one top-level subset.

Regression coverage:

```bash
uv run pytest tests/unit/sdk/codebase/test_rust_backend.py::test_rust_compact_top_level_symbol_lists_do_not_materialize_all_symbols -q
```

The test asserts that public top-level symbol lists use the dedicated compact subset methods and do not populate the full `_symbols` or `_symbol_handles` caches.

Measured on the cached Apache Airflow `2.10.5` checkout (`b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`) with `CodebaseConfig(graph_backend="rust", rust_fallback="error")`:

| Query path | Before wall | After wall | Before max RSS delta | After max RSS delta | Python handles created | Result count |
| ---------- | ----------: | ---------: | -------------------: | ------------------: | ---------------------: | -----------: |
| First `codebase.functions` | 0.310s | 0.031s | 104.8 MB | 0.0 MB | 52,339 -> 6,145 | 6,145 |
| First `codebase.classes` after functions | 0.0068s | 0.0267s | 0.0 MB | 0.0 MB | already hydrated -> 11,524 cumulative | 5,379 |
| First `codebase.symbols` after subsets | n/a | 0.112s | n/a | 0.0 MB | 23,663 cumulative | 23,663 |

The first high-value public query is now about 10x faster and avoids the previous 105 MB Python-side RSS spike. The follow-on subset calls do their own compact JSON round trip instead of reusing a fully hydrated all-symbol cache, which is an intentional tradeoff for large repos where memory pressure dominates. The aggregate `_symbol_handles_by_id` cache only contains handles actually requested by the public query path.

## Standalone TypeScript/JavaScript Rust Index Evidence

These measurements capture the first syntax-only Rust TypeScript/JavaScript index exposed through PyO3. The Rust path uses Python-selected file discovery for a fair file-list comparison. The later `Codebase` measurement below includes the current relative-import resolution, reference/dependency rows, and lazy Python shell handles.

The Next.js measurement was run on this branch on 2026-06-18 against `vercel/next.js` `v15.0.0` at commit `51bfe3c1863b191f4b039bc230e8ed5c57b0baf3`:

```bash
uv run python rust-rewrite/tools/benchmark_pinned_typescript_repo.py \
  --extension-dir /tmp/graph_sitter_py_ts_smoke \
  --skip-build-extension \
  --skip-fetch \
  --output /tmp/graph-sitter-nextjs-v15.0.0-benchmark.json
```

| Input                                                          | Python mode       | Python wall | Python max RSS | Python files | Python nodes | Rust TS index wall | Rust TS index max RSS | Rust selected files | Rust files | Rust symbols | Rust imports | Rust exports | Rust files with errors | Wall ratio | RSS ratio |
| -------------------------------------------------------------- | ----------------- | ----------: | -------------: | -----------: | -----------: | -----------------: | --------------------: | ------------------: | ---------: | -----------: | -----------: | -----------: | ---------------------: | ---------: | --------: |
| Next.js `v15.0.0` (`51bfe3c1863b191f4b039bc230e8ed5c57b0baf3`) | `--disable-graph` |     24.959s |      3100.1 MB |        13679 |       213969 |             3.347s |              200.3 MB |               13688 |      13688 |        23957 |        28210 |        16026 |                    114 |     7.457x |   15.475x |

The Rust selected-file count matches the Python `RepoOperator` selected file list exactly. Python materialized 9 fewer source-file objects because the repo includes intentionally broken/non-UTF-8 fixture files; Rust now records selected files and marks parser-error files instead of aborting or dropping the file.

## TypeScript Rust `Codebase` Construction Evidence

This measurement uses real `Codebase(...)` construction against the pinned Next.js checkout with `CodebaseConfig(graph_backend="rust", rust_fallback="error")`. It exercises compact TypeScript files, symbols, classes, functions, globals, interfaces, types, imports, exports, relative and tsconfig path/baseUrl import resolutions, references, dependencies, read-only function calls, and read-only Promise chains through the Python shell while keeping `CodebaseContext.nodes` blocked.

Command run on 2026-06-19:

```bash
uv run python rust-rewrite/tools/check_pinned_typescript_codebase.py \
  --skip-build-extension \
  --skip-fetch \
  --json
```

| Input                                                          | Rust `Codebase` wall | Rust `Codebase` max RSS | Files | Symbols | Imports | Exports | Import resolutions | References | Dependencies | Function calls | Promise chains | Python graph blocked |
| -------------------------------------------------------------- | -------------------: | ----------------------: | ----: | ------: | ------: | ------: | -----------------: | ---------: | -----------: | -------------: | -------------: | -------------------- |
| Next.js `v15.0.0` (`51bfe3c1863b191f4b039bc230e8ed5c57b0baf3`) |              10.771s |                435.2 MB | 13688 |   44871 |   28210 |   16027 |              13462 |     113809 |        49285 |         197581 |            878 | yes                  |

Compared with the Python TypeScript parse/object-materialization baseline above, the current Rust `Codebase` TypeScript shell is about 2.317x faster and about 7.123x lower max RSS while exposing compact export, call, and Promise-chain handles and keeping the eager Python graph unbuilt. The pinned proof also validates a real `packages/next/src/cli/next-lint.ts` file/symbol lookup for 27 file-local call records, 16 `nextLint` symbol call records, and one `.then/.catch` Promise chain without materializing the full call or chain caches. JSX traversal now records component tag references while skipping lowercase intrinsic tags and prop-name false positives. A parser fallback tries the TS grammar for `.ts`/`.js` files and keeps the lower-error parse, reducing pinned Next.js parser-error files from 114 to 113 by recovering `test/integration/typescript/components/angle-bracket-type-assertions.ts`.

The same proof is now available as an opt-in test gate:

```bash
uv run python rust-rewrite/tools/check_pinned_typescript_codebase.py \
  --skip-build-extension \
  --skip-fetch
```

On 2026-06-19, the full pinned large-repo gate validated exact pinned Next.js `Codebase` handle counts plus compact function-call and Promise-chain counts, confirmed the Python graph stayed blocked, and measured 10.771s wall / 435.2 MB max RSS. Against the recorded Python TypeScript parse/object-materialization baseline above, that is 2.317x faster wall time and 7.123x lower max RSS with conservative CI-style ceilings.

## Installed-Wheel `uvx` Airflow Evidence

The branch-built wheel path now has an artifact-level large Python proof that
runs through `uvx --from dist/<wheel>.whl graph-sitter`, not through an
editable checkout or manually copied extension.

Command run on 2026-06-19:

```bash
uv run python rust-rewrite/tools/check_wheel_pinned_python_repo.py \
  --wheel dist/graph_sitter-0.56.15.dev166+g2f790c9f7.d20260619-cp313-cp313-macosx_26_0_arm64.whl \
  --skip-fetch \
  --compare-python-backend \
  --min-parse-elapsed-ratio 1.5 \
  --min-sampled-rss-ratio 3.0 \
  --output /tmp/graph-sitter-airflow-wheel-rust-vs-python.json
```

| Input                                                                | Installed backend | Parse elapsed | `uvx` outer wall | Sampled process-tree RSS | Files | Symbols | Imports | References | External references | Dependencies |
| -------------------------------------------------------------------- | ----------------- | ------------: | ---------------: | -----------------------: | ----: | ------: | ------: | ---------: | ------------------: | -----------: |
| Apache Airflow `2.10.5` (`b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`) | Rust strict       |        4.913s |           6.064s |                 487.0 MB |  4789 |   52339 |   45404 |     117799 |               78784 |        77570 |
| Apache Airflow `2.10.5` (`b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`) | Python            |       48.242s |          77.649s |                5429.3 MB |  4789 |   27728 |   44100 |        n/a |                 n/a |      1099202 |

The installed-wheel strict Rust path matched the committed compact Python golden
summary at the time that wheel was built, including 4,789 files, 52,339 symbols,
45,404 imports, 117,799 references, 78,784 external references, 77,570
dependencies, and zero files with parse errors. A later source fix for
parenthesized Python `from ... import (...)` extraction updates the committed
golden counts. Compared with the installed-wheel Python backend on the same
checkout and wheel, the Rust path was 9.818x faster by CLI parse elapsed and
11.148x lower by sampled process-tree RSS.

The same branch-built wheel gate also proves a real pinned Airflow transform
through the distributed CLI:

```bash
uv run python rust-rewrite/tools/check_wheel_pinned_python_repo.py \
  --wheel dist/graph_sitter-0.56.15.dev166+g2f790c9f7.d20260619-cp313-cp313-macosx_26_0_arm64.whl \
  --skip-fetch \
  --run-transform-proof \
  --output /tmp/graph-sitter-airflow-wheel-transform.json
```

That run parsed pinned Airflow in strict Rust mode, cloned a temporary mutable
checkout, ran `graph-sitter transform ... --language python --backend rust --fallback error --write` through `uvx --from`, added `from typing import Any`
to `airflow/__init__.py`, renamed `__getattr__` to
`__getattr_wheel_proof__`, and asserted only `airflow/__init__.py` changed.

| Operation                             |   Wall | Sampled process-tree RSS | Validation                         |
| ------------------------------------- | -----: | -----------------------: | ---------------------------------- |
| Installed-wheel strict Rust parse     | 5.052s |                 503.5 MB | matched compact golden summary     |
| Installed-wheel strict Rust transform | 5.920s |                 500.1 MB | only `airflow/__init__.py` changed |

## Installed-Wheel `uvx` Next.js Evidence

The branch-built wheel path now has an artifact-level large TypeScript proof
that runs through `uvx --from dist/<wheel>.whl graph-sitter`, not through an
editable checkout or manually copied extension.

Command run on 2026-06-19:

```bash
uv run python rust-rewrite/tools/check_wheel_pinned_typescript_repo.py \
  --wheel dist/graph_sitter-0.56.15.dev166+g2f790c9f7.d20260619-cp313-cp313-macosx_26_0_arm64.whl \
  --skip-fetch \
  --compare-python-backend \
  --min-parse-elapsed-ratio 1.5 \
  --min-sampled-rss-ratio 3.0 \
  --output /tmp/graph-sitter-nextjs-wheel-rust-vs-python.json
```

| Input                                                          | Installed backend | Parse elapsed | `uvx` outer wall | Sampled process-tree RSS | Files | Symbols | Imports | Exports | References | Dependencies |
| -------------------------------------------------------------- | ----------------- | ------------: | ---------------: | -----------------------: | ----: | ------: | ------: | ------: | ---------: | -----------: |
| Next.js `v15.0.0` (`51bfe3c1863b191f4b039bc230e8ed5c57b0baf3`) | Rust strict       |       10.352s |          11.508s |                 537.5 MB | 13688 |   44870 |   28210 |   16026 |     114463 |        49287 |
| Next.js `v15.0.0` (`51bfe3c1863b191f4b039bc230e8ed5c57b0baf3`) | Python            |       57.956s |          78.107s |                4505.6 MB | 13679 |   25364 |   28723 |   17878 |        n/a |       811914 |

The installed-wheel strict Rust path matched the committed compact TypeScript
golden summary at the time that wheel was built, including 13,688 files, 44,870
symbols, 28,210 imports, 16,026 exports, 114,463 references, 49,287
dependencies, 25,318 external references, 160 subclass edges, and 114 files with
parse errors. A later source fix for TS angle-bracket assertion parsing updates
the committed golden counts. Compared with the installed-wheel Python backend
on the same checkout and wheel, the Rust path was 5.598x faster by CLI parse
elapsed and 8.383x lower by sampled process-tree RSS. The Python backend
materialized 9 fewer file objects than Rust selected files, matching the known
selected-file versus materialized-file delta for this repo's broken fixture
files.

The same branch-built wheel gate also proves a real pinned Next.js transform
through the distributed CLI:

```bash
uv run python rust-rewrite/tools/check_wheel_pinned_typescript_repo.py \
  --wheel dist/graph_sitter-0.56.15.dev166+g2f790c9f7.d20260619-cp313-cp313-macosx_26_0_arm64.whl \
  --skip-fetch \
  --run-transform-proof \
  --output /tmp/graph-sitter-nextjs-wheel-transform.json
```

That run parsed pinned Next.js in strict Rust mode, cloned a temporary mutable
checkout, ran `graph-sitter transform ... --language typescript --backend rust --fallback error --write` through `uvx --from`, added
`import { act } from 'react-dom/test-utils';` to
`packages/next/src/client/components/app-router-announcer.tsx`, renamed
`AppRouterAnnouncer` to `AppRouterAnnouncerWheelProof`, and rewrote the
importing usage in `packages/next/src/client/components/app-router.tsx`.

| Operation                             |    Wall | Sampled process-tree RSS | Validation                                                   |
| ------------------------------------- | ------: | -----------------------: | ------------------------------------------------------------ |
| Installed-wheel strict Rust parse     | 10.386s |                 549.7 MB | matched compact golden summary                               |
| Installed-wheel strict Rust transform | 11.834s |                 525.8 MB | only `app-router-announcer.tsx` and `app-router.tsx` changed |

## Pinned Compact Snapshot Evidence

The first committed large-repo compact snapshot is `rust-rewrite/golden/apache-airflow-2.10.5-rust-compact.json`. It was generated from Apache Airflow `2.10.5` at commit `b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`.

| Graph family       |  Count | SHA-256                                                            |
| ------------------ | -----: | ------------------------------------------------------------------ |
| Files              |   4789 | `226e8cb32dc0a23ec956e97b036e7c505037df979cce7182514f39a43b07cb80` |
| Symbols            |  52339 | `d4b75c9c6d82b1d30424845c86b88c9fb18ca7748fc088c16b4cfca00de30699` |
| Imports            |  40580 | `fe4a595d850f2f57f1eb1a5ca347ecfcc09259e31cd7b44306902c04de7275d0` |
| Import resolutions |  19011 | `84df9ba7bf069278f61ac2a4891d8b4cb38b25f4f63ce20dd77eada1ba654278` |
| References         | 109817 | `d7ab546586eb968f35dd1bf8f109db6a54b889af464a2c349e7af2e38ea60a8a` |
| Dependencies       |  71932 | `cbf361a2b46e5ea2e5cad352c5abe8ab493869eb422cbdb77912484ea9fab1d1` |

The snapshot tool also validates internal compact graph integrity: import-resolution links, reference links, dependency links, dependency reference counts, and dependency reference source/target consistency must all be zero-mismatch before the snapshot can pass.

Important caveats:

- The Rust indexer currently extracts a compact subset: files, top-level Python classes/functions/globals, nested Python class/function records for source attribution, imports, internal import-resolution records, first-slice Python symbol reference records, and de-duplicated dependency records for indexed Python modules.
- Direct package re-exports and wildcard import/re-export chains are resolved for indexed internal modules when the package file exposes a matching imported binding. Static literal `__all__` assignments restrict wildcard expansion; dynamic `__all__` construction, order-sensitive wildcard binding semantics, and ambiguous external re-export chains remain future work.
- Public Python handles still expose top-level `Codebase.symbols`, `classes`, and `functions`; nested compact symbols are currently internal records for dependency-source precision and `file.symbols(nested=True)`.
- Function parameters, lambda parameters, local assignment targets, local imports, `for` targets, `with ... as ...` targets, `except ... as ...` targets, comprehension targets, match-pattern captures, nested definitions, and `nonlocal` declarations now shadow imported/top-level names in the compact reference pass, reducing false-positive dependency edges before full lexical scope tables exist. Comprehension targets are scoped to the comprehension expression instead of leaking to the whole enclosing function. `global` declarations now remove matching names from the local-shadow set so module-level writes and uses remain visible in the compact reference/dependency graph.
- Imported module member references such as `module.some_func`, `alias.SomeClass`, `pkg.module.some_func`, and namespace-style nested module chains like `from a import b; b.c.d()` now resolve when the qualifier maps to an indexed internal Python module. Other attribute field names are skipped as bare-name references until full attribute/type resolution exists. The object side of an attribute expression is still scanned, so `helper.attr` preserves the `helper` reference while `obj.helper` no longer pretends `helper` is a standalone symbol use.
- The Python-facing Rust facade uses Python's selected file list, but the compact Rust records are not yet full Python graph parity. Symbol and import totals should not be compared directly with current Python graph node totals until the resolver and lazy handle layers are implemented.
- The Python backend numbers include the current eager Python object materialization and, in full graph mode, dependency edge computation.
- The Rust RSS number is sampled from a short-lived release process; it is suitable for directional comparison, not allocator-level attribution.
- The TypeScript/JavaScript Rust path now emits compact files, symbols, imports, exports, parser-error status, relative and tsconfig path/baseUrl import-resolution rows, first-slice reference rows, dependency rows, and lazy `Codebase` compatibility handles. External module modeling, lexical/type/interface parity, and codemod parity remain future work.
- The generated fixture, this repo, and the pinned Airflow baseline are useful proof points, but Python-vs-Rust semantic parity snapshots and additional canonical repos are still open.

## Open Questions

- Which additional small, medium, and huge repositories should become canonical Phase 0 baselines?
- Should TypeScript baselines run with dependency manager and language engine flags off, on, or both?
- Do we need allocator-level attribution with `memray`, `tracemalloc`, or `py-spy` in addition to RSS sampling?
- What commit, dependency lockfile, and Python minor version should define the official baseline?
- Which memory target should be set for the first Rust vertical slice: total RSS, graph-only delta, or parse-only delta?
