# Rust Rewrite Strategy

## Goal

Replace the memory-heavy Python object graph with a compact Rust engine while preserving the current Python-facing API. The Python shell should remain the user and codemod interface; Rust should own parsing, indexing, symbol/import/export resolution, dependency graph storage, and eventually incremental invalidation.

The main problem to solve is not just CPU time. The current architecture eagerly materializes the codebase as many Python objects, keeps tree-sitter nodes and parent/context/file links on those objects, stores the same objects in `rustworkx.PyDiGraph`, and maintains additional per-file node lists and range indexes. On very large repos this can inflate into tens of GB of resident memory.

## Strategy

Build a Rust core behind the existing Python API:

1. Keep `Codebase`, `SourceFile`, `Symbol`, `Import`, `Export`, and related Python classes as compatibility handles.
2. Move canonical storage into Rust:
   - interned paths, strings, import specifiers, symbol names
   - compact `FileId`, `NodeId`, `SymbolId`, `ImportId`, `ExportId`, `EdgeId`
   - arena/slotmap-backed records instead of Python objects
   - adjacency tables or compressed graph storage instead of `PyDiGraph` payloads
   - byte ranges and kind enums instead of persistent Python `tree_sitter.Node` wrappers for every node
3. Create Python wrappers lazily only when user code asks for them.
4. Run graph queries in Rust and return IDs or compact records; Python adapts those into existing objects/lists.
5. Port incrementally behind a backend flag, keeping the Python backend available until parity is proven.

## Non-Goals

- Do not rewrite the public codemod API first.
- Do not translate every Python class one-for-one into Rust.
- Do not make Rust own all edit formatting in the first slice.
- Do not remove the current Python backend until large-repo memory and parity targets are met.

## Current Hot Spots To Replace

- `CodebaseContext` owns a `rustworkx.PyDiGraph` of Python node payloads.
- `SourceFile` eagerly parses and stores all parsed nodes in `_nodes`.
- `Editable` objects keep `ts_node`, `ctx`, `parent`, and file/node IDs.
- Initial graph build parses every source file and then runs import/export/dependency passes over the aggregate node set.
- Dependency recomputation uses object methods and fixed-point list expansion rather than compact indexed frontiers.
- Public queries such as `codebase.symbols`, `codebase.imports`, and `codebase.files` materialize Python lists by filtering graph nodes.

## Target Architecture

### Rust Crates

- `graph_sitter_engine`
  - core data model
  - tree-sitter parsing
  - compact indexes
  - import/export/name/scope resolution
  - dependency graph
  - incremental invalidation
  - debug dumps and benchmark hooks
- `graph_sitter_py`
  - PyO3 bindings
  - backend facade used by Python `CodebaseContext`
  - lazy handle constructors

### Python Integration

- Add a backend option such as `CodebaseConfig(graph_backend="python" | "rust")`.
- Introduce an engine facade under `CodebaseContext`.
- Keep current Python objects for compatibility, but make Rust-backed versions hold IDs instead of owning canonical state.
- Keep the existing transaction manager initially; Rust should provide ranges and patch intents, not own all formatting in phase 1.

### Data Model

Minimum records for the vertical slice:

- `FileRecord`: path ID, language, content hash, root range, per-file node ranges
- `SymbolRecord`: file ID, name ID, full-name ID, kind, parent symbol, scope, range, declaration range
- `ImportRecord`: file ID, module/name/alias IDs, import kind, range, statement range
- `ExportRecord`: file ID, exported name, target symbol/import/file, range
- `UsageRecord`: file ID, source node, target node, usage kind/type, match range
- `GraphEdge`: source ID, target ID, edge kind, optional usage ID

## Multi-Agent Work Convention

This file is the shared coordination ledger for helper agents.

- Every task must be represented as a Markdown checkbox line.
- Use `[ ]` for open or claimed work and `[x]` for completed work.
- To claim a task, append `owner: <agent-name>` to the same checkbox line.
- To mark a task blocked, keep it unchecked and append `BLOCKED: <reason>`.
- When completing a task, change `[ ]` to `[x]` and append a short result note.
- Add new tasks under the relevant phase rather than creating a separate tracking file.
- Each agent should append a short entry to `Agent Log` when it starts or finishes meaningful work.
- Avoid broad edits to sections owned by another active agent; add notes instead.
- Keep implementation-specific findings near the task they affect.

Recommended task format:

```md
- [ ] Short imperative task title. owner: agent-name. Notes: current finding or next action.
- [x] Completed task title. owner: agent-name. Result: concise outcome.
```

## Agent Hierarchy

- [ ] Lead/RFC agent: maintain this strategy, define interfaces, arbitrate scope, and keep phases coherent.
- [ ] Benchmark agent: measure current memory/time by phase on small, medium, and huge repos.
- [ ] API inventory agent: enumerate public APIs and classify P0/P1/P2 compatibility requirements.
- [ ] Rust data-model agent: design compact arenas, IDs, interners, and graph storage.
- [ ] Parser/index agent: implement Rust tree-sitter extraction into compact IR.
- [ ] Resolver agent: port import, export, scope, name, superclass, and dependency resolution.
- [ ] PyO3 binding agent: expose Rust engine operations to the existing Python package.
- [ ] Incremental agent: design file add/reparse/delete invalidation and stable ID behavior.
- [ ] Parity/test agent: run existing tests against both backends and build golden graph snapshots.
- [ ] Packaging/CI agent: integrate Rust builds with the current hatch/Cython packaging and CI.

## Active Worktrees

- [x] Benchmarks/profiling. owner: Poincare. Agent: `019edc37-802c-7223-8d37-75a51b65abbd`. Branch: `codex/rust-rewrite-benchmarks`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-benchmarks`. Result: benchmark plan and Python backend harness committed.
- [x] API inventory. owner: Dewey. Agent: `019edc37-82ff-7b92-9fac-5364e2d8098b`. Branch: `codex/rust-rewrite-api-inventory`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-api-inventory`. Result: P0/P1/P2 API compatibility inventory committed.
- [x] Rust data model. owner: Pasteur. Agent: `019edc37-859c-71b2-b884-ab7a2bfc707e`. Branch: `codex/rust-rewrite-data-model`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-data-model`. Result: compact Rust-side schema and migration risks committed.
- [x] Parser/index vertical slice. owner: Meitner. Agent: `019edc37-8867-7a83-a18e-b0ec0ca29d11`. Branch: `codex/rust-rewrite-parser-index`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-parser-index`. Result: parser/index extraction plan committed.
- [x] Resolver/dependency algorithms. owner: Gauss. Agent: `019edc37-8c34-7f93-b0ae-746cbd579962`. Branch: `codex/rust-rewrite-resolver`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-resolver`. Result: resolver algorithm inventory and Rust port plan committed.
- [x] Rust engine skeleton. owner: Beauvoir. Agent: `019edc37-8f2d-7dd3-b3ed-a1f9e1b191a7`. Branch: `codex/rust-rewrite-engine-skeleton`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-engine-skeleton`. Result: standalone Cargo workspace and smoke tests committed.
- [x] PyO3/Python compatibility. owner: Wegener. Agent: `019edc4e-72b1-7a00-8644-e43503f0cdc3`. Branch: `codex/rust-rewrite-pyo3-compat`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-pyo3-compat`. Result: compatibility plan committed.

## Phase 0: Baseline, RFC, And Contracts

- [x] Add memory benchmark harness for current Python backend. owner: Poincare. Result: added `rust-rewrite/tools/measure_python_backend.py`.
- [x] Measure initial cold parse RSS and wall time for generated fixture and this repo. owner: codex. Result: recorded in `rust-rewrite/benchmarks.md`.
- [x] Add pinned Python repository benchmark harness. owner: codex. Result: added `rust-rewrite/tools/benchmark_pinned_python_repo.py` to clone/fetch a pinned repo, build the PyO3 extension, run Python and Rust `Codebase` measurements, and enforce wall/RSS/file-count gates.
- [x] Measure first canonical huge Python repo cold parse/Rust compact backend baseline. owner: codex. Result: Apache Airflow `2.10.5` at `b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf` records 4,789 Python files, 6.218x wall improvement, and 9.882x max-RSS improvement for the current compact Rust slice.
- [ ] Measure cold parse RSS and wall time for additional canonical small, medium, and huge repos.
- [ ] Measure graph node/edge counts, Python object counts, and per-phase allocation peaks.
- [x] Document the exact current build phases with timings: file enumeration, parse, directory tree, config parse, import resolution, export resolution, dependency recompute. owner: Poincare. Result: added phase map in `rust-rewrite/benchmarks.md`; representative repo timings remain open.
- [x] Inventory all public `Codebase` properties and methods. owner: Dewey. Result: documented in `rust-rewrite/api-inventory.md`.
- [x] Inventory all public `SourceFile`, `Symbol`, `Import`, `Export`, and `Directory` APIs used by tests/docs. owner: Dewey. Result: documented in `rust-rewrite/api-inventory.md`.
- [x] Define P0 compatibility surface for the first Rust backend slice. owner: Dewey. Result: documented in `rust-rewrite/api-inventory.md`.
- [ ] Define large-repo success targets for memory and time.
- [x] Select first pinned large Python repo commit for golden parity and latency benchmarks. owner: codex. Result: Apache Airflow `2.10.5`, upstream `https://github.com/apache/airflow.git`, ref `refs/tags/2.10.5`, commit `b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`, measured with Python 3.13.11 on macOS.
- [ ] Select additional pinned large Python repo commits for golden parity and latency benchmarks.
- [x] Build first compact Rust golden graph snapshot for the pinned large Python repo commit. owner: codex. Result: committed `rust-rewrite/golden/apache-airflow-2.10.5-rust-compact.json` with stable files, symbols, imports, import-resolution, reference, and dependency counts/hashes/samples plus integrity checks.
- [ ] Compare golden reference/import/dependency graph snapshots against the Python backend semantics for the pinned large Python repo commits. Notes: fixtures should assert file/module records, import graph edges, symbol reference graph edges, dependency graph edges, and deterministic sort order.
- [x] Draft compact Rust data model with module boundaries and Python integration points. owner: Pasteur. Result: documented in `rust-rewrite/data-model.md`.
- [ ] Draft full Rust engine RFC with module boundaries and Python integration points.
- [ ] Decide build tooling: `maturin`, setuptools-rust, or hatch custom hook.

## Phase 1: Rust Engine Skeleton

- [x] Add Rust workspace/crate skeleton without changing default behavior. owner: Beauvoir. Result: added standalone Cargo workspace under `crates/`.
- [x] Add PyO3 module import smoke test. owner: codex. Result: built the extension module and imported it from Python, then indexed this repo through `index_python_path`.
- [x] Add `graph_backend` config flag with default `python`. owner: codex. Result: added `GraphBackend` and `RustFallbackMode` to `CodebaseConfig`.
- [x] Add compact Rust index facade that can be constructed from `CodebaseContext`. owner: codex. Result: `ctx.rust_index` builds through the optional PyO3 extension when `graph_backend` is `rust` or `auto`.
- [x] Skip eager Python graph construction in opt-in Rust compact mode. owner: codex. Result: `CodebaseConfig(graph_backend="rust")` leaves the Python graph unbuilt when the Rust compact index succeeds.
- [ ] Add full Rust engine facade object that can back existing `CodebaseContext` graph query APIs.
- [x] Add a minimal debug API returning engine version and enabled features. owner: Beauvoir. Result: added Rust `Engine::debug_info` and feature-gated PyO3 bindings.
- [ ] Add CI job that builds the Rust extension on supported Python versions.
- [x] Add benchmark command comparing Python backend with Rust compact indexer. owner: codex. Result: added `rust-rewrite/tools/compare_rust_python_index.py`.
- [x] Add benchmark command for the Python-facing Rust facade. owner: codex. Result: added `rust-rewrite/tools/measure_rust_facade.py`.
- [x] Add benchmark command for real `Codebase` construction with the Rust compact backend. owner: codex. Result: added `rust-rewrite/tools/measure_codebase_rust_backend.py`.
- [x] Add benchmark command that can select full `Codebase` `--backend python|rust` once Rust backend is wired into Python. owner: codex. Result: `benchmark_pinned_python_repo.py` runs Python and Rust `Codebase` measurements in child processes for pinned external repos.

## Phase 2: Parser And Compact Index Vertical Slice

- [x] Specify parser/index vertical slice and extraction rules. owner: Meitner. Result: documented in `rust-rewrite/parser-index.md`.
- [x] Implement standalone Rust Python file discovery for the first compact-index slice. owner: codex. Result: recursive repo walk with common generated/cache directory skips.
- [x] Implement Rust file discovery input format from Python repo operator. owner: codex. Result: added selected-file `index_python_paths` API and pass `RepoOperator.iter_files(...)` results from `CodebaseContext`.
- [x] Implement tree-sitter parser setup for Python. owner: codex. Result: `graph-sitter-engine` uses `tree-sitter-python` and indexes Python files.
- [ ] Implement tree-sitter parser setup for TypeScript/TSX.
- [ ] Extract file records with path, language, content hash, and root ranges.
- [x] Extract file records with path, byte length, line count, error status, and root ranges for Python. owner: codex.
- [x] Extract top-level Python classes and functions. owner: codex. Result: compact `SymbolRecord` extraction for class/function definitions and decorated definitions.
- [x] Extract top-level Python globals. owner: codex. Result: added compact global-variable symbol records for simple top-level assignments and annotated assignments.
- [ ] Extract top-level TypeScript classes, functions, interfaces, type aliases, enums, and globals.
- [x] Extract imports for Python. owner: codex. Result: compact `ImportRecord` extraction for `import`, `from`, and future imports.
- [ ] Extract imports and exports for TypeScript.
- [ ] Build path and string interners.
- [x] Expose compact Python index summary and JSON through PyO3. owner: codex. Result: added `PythonIndex`, `IndexSummary`, `Engine.index_python_path`, and module-level `index_python_path`.
- [x] Expose compact Python file, symbol, import, and import-resolution records through PyO3/Python facade. owner: codex. Result: added record-family JSON methods and typed Python dataclass accessors on `RustIndexBackend`.
- [ ] Expose `files`, `symbols`, `classes`, `functions`, `imports`, and `exports` ID queries through PyO3.
- [x] Add golden snapshots for compact IR on small Python fixtures. owner: codex. Result: added deterministic compact graph snapshot covering files, symbols, imports, and import resolutions.
- [ ] Add golden snapshots for compact IR on small TypeScript fixtures.

## Phase 3: Resolution And Dependency Graph

- [x] Inventory current resolver/dependency algorithms and Rust relation-table plan. owner: Gauss. Result: documented in `rust-rewrite/resolution-algorithms.md`.
- [ ] Port Python import resolution rules.
- [x] Implement compact Python import-to-file and import-to-symbol resolution for indexed internal modules. owner: codex. Result: Rust now emits `ImportResolutionRecord` rows for direct, absolute `from`, and relative `from` imports when targets are inside the selected file set.
- [ ] Port TypeScript relative import resolution rules.
- [ ] Port TypeScript config/path alias handling.
- [ ] Represent external modules compactly.
- [ ] Implement full import-to-file and import-to-symbol edges for all Python and TypeScript rules.
- [ ] Implement export-to-symbol/import/file edges.
- [ ] Implement lexical scope tables for name resolution.
- [x] Implement first compact Python symbol reference extraction by identifier ranges. owner: codex. Result: records same-file and imported top-level symbol references inside top-level Python classes/functions.
- [x] Attribute compact Python references to nested class/function source symbols. owner: codex. Result: nested Python functions and methods are indexed as non-top-level compact symbols, while public `Codebase.functions` remains top-level-only.
- [x] Exclude compact Python references shadowed by parameters, local assignments, and nested definitions. owner: codex. Result: avoids resolving local bindings to imported/top-level symbols and reduced Airflow compact references from 112,238 to 105,739.
- [x] Exclude compact Python references shadowed by local imports. owner: codex. Result: avoids resolving function-local `import ... as ...`, `import pkg.mod`, and `from ... import ...` bindings to imported/top-level symbols; reduced Airflow compact references from 105,739 to 105,624 and dependencies from 68,927 to 68,869.
- [x] Exclude compact Python references shadowed by control-flow bindings. owner: codex. Result: avoids resolving `for` targets, `with ... as ...` targets, and `except ... as ...` targets to imported/top-level symbols; reduced Airflow compact references from 105,624 to 105,467 and dependencies from 68,869 to 68,848.
- [x] Exclude compact Python references shadowed by comprehension targets and match-pattern captures. owner: codex. Result: avoids resolving comprehension loop targets and match capture patterns to imported/top-level symbols; reduced this checkout's compact references from 4,101 to 4,089 and dependencies from 2,950 to 2,949. The pinned Airflow `2.10.5` compact graph stayed at 105,467 references and 68,848 dependencies.
- [x] Scope compact Python comprehension target shadows to comprehension expressions. owner: codex. Result: comprehension loop targets no longer hide later references in the enclosing function; current checkout and pinned Airflow stayed graph-stable at 4,110 and 104,622 references respectively after the attribute-field skip baseline.
- [x] Exclude compact Python references shadowed by lambda parameters. owner: codex. Result: adds range-scoped lambda-body bindings so lambda parameters shadow inside the lambda body without hiding legitimate default-value references such as `lambda local=Base: local`; this checkout and pinned Airflow stayed graph-stable at 4,089 and 105,467 references respectively.
- [x] Preserve compact Python references for `global` declarations. owner: codex. Result: `global` names are removed from the function-local shadow set, so module-level writes and uses remain visible; Airflow compact coverage now emits 105,607 references and 68,917 dependencies.
- [x] Stop treating Python attribute field names as bare compact references. owner: codex. Result: scans the object side of attribute expressions but skips the field-name side; Airflow compact coverage now emits 104,622 references and 68,340 dependencies.
- [x] Resolve compact Python references through imported module attributes. owner: codex. Result: resolves `module.some_func`, `alias.SomeClass`, and `pkg.module.some_func` when the qualifier maps to an indexed internal Python module; Airflow compact coverage now emits 109,282 references and 71,534 dependencies.
- [x] Exclude compact Python references shadowed by `nonlocal` declarations. owner: codex. Result: prevents closure variables declared `nonlocal` from resolving to imported/top-level symbols in nested functions; this checkout and pinned Airflow stayed graph-stable at 4,110 and 109,282 references respectively.
- [x] Resolve direct Python package re-export imports. owner: codex. Result: `from pkg import Symbol` follows matching imported bindings in `pkg/__init__.py` to the original internal symbol; Airflow compact coverage now emits 109,655 references and 71,788 dependencies.
- [x] Resolve Python wildcard import and re-export chains. owner: codex. Result: compact exported-name tables now propagate `from module import *` across indexed internal modules and feed named imports, references, and dependency edges; Airflow compact coverage now emits 109,743 references and 71,863 dependencies.
- [x] Resolve nested Python module attribute references. owner: codex. Result: module-prefix bindings now resolve namespace-style chains such as `from a import b; b.c.d()` and `import a.b; a.b.c.d()` to indexed internal module symbols; Airflow compact coverage now emits 109,817 references and 71,932 dependencies.
- [x] Restrict Python wildcard imports with static `__all__` exports. owner: codex. Result: literal top-level `__all__` list/tuple/set assignments now constrain compact wildcard expansion while explicit named imports still resolve; pinned Airflow stayed graph-stable at 109,817 references and 71,932 dependencies.
- [ ] Expand symbol usage extraction to full lexical shadowing behavior, full attribute/type resolution, and order-sensitive scopes.
- [x] Implement first compact dependency edge construction from usage records. owner: codex. Result: emits de-duplicated Python `DependencyRecord` edges from compact references with contributing reference IDs.
- [ ] Expand dependency edge construction to full lexical/reference coverage, external modules, and TypeScript.
- [ ] Implement superclass/interface dependency edges.
- [ ] Add graph debug dump for nodes, edges, and usage metadata.
- [x] Add compact Rust graph debug snapshot for pinned Airflow. owner: codex. Result: `snapshot_pinned_python_repo.py` normalizes compact records by stable paths/symbol keys and emits deterministic counts, hashes, and sample rows for large-repo review.
- [ ] Add parity tests comparing Python backend and Rust backend graph edges on fixtures.

## Phase 4: Lazy Python Compatibility Layer

- [x] Plan Python/PyO3 compatibility layer and lazy handle migration. owner: Wegener. Result: documented in `rust-rewrite/python-compat.md`.
- [x] Add temporary Python compact handle base for Rust record-backed read APIs. owner: codex. Result: added `RustCompactHandle` with stable compact node IDs for files, symbols, and imports.
- [ ] Implement Rust-backed file handles for P0 `SourceFile` APIs.
- [ ] Implement Rust-backed symbol handles for P0 `Symbol`, `Class`, and `Function` APIs.
- [ ] Implement Rust-backed import handles for P0 `Import` APIs.
- [ ] Implement Rust-backed export handles for P0 TypeScript `Export` APIs.
- [x] Make `Codebase.files` return compact read handles under the Python Rust backend. owner: codex.
- [x] Make `Codebase.symbols`, `classes`, `functions`, `global_vars`, and `imports` return compact read handles under the Python Rust backend. owner: codex.
- [x] Expose compact Rust file inbound import handles. owner: codex. Result: `RustCompactFile.inbound_imports` and `importers` now read from compact import-resolution records without materializing the Python graph.
- [x] Expose compact Rust file import lookup APIs. owner: codex. Result: `RustCompactFile.import_statements`, `has_import`, and `get_import` now read from compact import records and support alias/module/source lookup without materializing the Python graph.
- [x] Expose compact Rust symbol dependency and usage handles. owner: codex. Result: `RustCompactSymbol.dependencies`, `usages`, and `symbol_usages` now read from compact dependency/reference records with property and callable access.
- [x] Expose compact Rust import usage handles. owner: codex. Result: `RustCompactImport.usages` and `symbol_usages` now read from compact references grouped by `import_id` with property and callable access.
- [ ] Make TypeScript `Codebase.exports`, `interfaces`, and `types` return lazy handles under Rust backend.
- [ ] Preserve existing sorting behavior for public query results.
- [ ] Add fallback path to Python backend for unsupported methods.
- [x] Add tests that verify no full Python object graph is materialized for simple list queries. owner: codex.

## Phase 5: Incremental Sync And Edits

- [ ] Define stable ID behavior across file reparse.
- [ ] Implement add file in Rust backend.
- [ ] Implement delete file in Rust backend.
- [ ] Implement reparse changed file in Rust backend.
- [ ] Implement dependency invalidation frontier based on changed imports, exports, symbols, and usages.
- [ ] Integrate Rust backend with existing `apply_diffs`.
- [ ] Integrate Rust backend with existing transaction commit flow.
- [ ] Preserve Python transaction manager as first edit backend.
- [ ] Add parity tests for rename/move/add-import flows on Rust backend.
- [ ] Add stress tests for repeated incremental edits.

## Phase 6: Hardening And Rollout

- [ ] Run full unit suite with Python backend.
- [ ] Run full unit suite with Rust backend where supported.
- [ ] Add large-repo memory regression benchmark to CI or nightly.
- [x] Add pinned large-repo latency/RSS benchmark harness. owner: codex. Result: Airflow `2.10.5` benchmark command emits backend, wall time, max RSS, file count, node/edge counts, compact Rust record counts, mismatch summaries, and pass/fail gates.
- [x] Add opt-in pinned large-repo compact snapshot test. owner: codex. Result: `tests/integration/rust_rewrite/test_pinned_airflow_snapshot.py` runs the committed Airflow compact golden check when `GRAPH_SITTER_RUN_PINNED_AIRFLOW_SNAPSHOT=1`.
- [ ] Add pinned large-repo parity test for reference graph, import graph, dependency graph, and latency/RSS. Notes: start with Apache Airflow `2.10.5` at commit `b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf`; assert reference graph, import graph, dependency graph, deterministic ordering, and benchmark wall/RSS against the exact checkout before adding more canonical repos.
- [ ] Add feature flag documentation.
- [ ] Add migration notes for unsupported APIs.
- [ ] Decide default backend criteria.
- [ ] Flip default to Rust only after memory, speed, and parity targets are met.
- [ ] Keep Python backend available for one release after Rust becomes default.

## Acceptance Targets

- [ ] Cold parse memory on a representative huge repo is less than 25% of current Python backend.
- [ ] Cold parse wall time is no slower than current Python backend, with a target of at least 2x faster.
- [ ] P0 query APIs have parity with current behavior.
- [ ] Existing unit tests pass for Python backend throughout the rewrite.
- [ ] Rust backend has golden snapshots for graph IR and dependency edges.
- [ ] Unsupported Python APIs fail explicitly or fall back to Python backend.

## Agent Log

- [x] 2026-06-18: Initial strategy file created on `rust-rewrite` branch. owner: codex. Notes: ready for helper agents to claim phase tasks.
- [x] 2026-06-18: Integrator created seven worktrees and spawned six helper agents; PyO3 compatibility was queued due to agent concurrency limit. owner: codex.
- [x] 2026-06-18: Six completed helper branches reviewed and their artifacts staged for integration. owner: codex. Notes: PyO3 compatibility agent is now running as Wegener.
- [x] 2026-06-18: PyO3 compatibility helper completed and its planning artifact was staged for integration. owner: codex.
- [x] 2026-06-18: Implemented first Rust Python compact-index slice and benchmark comparison; initial measurements show 9x-22x wall-time improvement and 70x-104x RSS improvement on this repo for the implemented slice. owner: codex.
- [x] 2026-06-18: Exposed the compact Python index through the PyO3 module and verified a Python import smoke against this repo. owner: codex. Notes: extension returned 1127 files, 3117 symbols, and 6414 imports for the current checkout.
- [x] 2026-06-18: Added Python-shell Rust index integration behind `CodebaseConfig(graph_backend=...)`, selected-file PyO3 indexing from `RepoOperator`, and a facade benchmark. owner: codex. Notes: selected-file facade matched Python's 1129-file discovery and ran 4.7x faster with 4.7x lower process max RSS than Python parse/object materialization on this checkout.
- [x] 2026-06-18: Added compact Rust Python import resolution records. owner: codex. Notes: the Python-facing Rust facade now emits 432 internal import-resolution records on this checkout and remains 4.3x faster with 4.6x lower process max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added typed Python facade accessors and a deterministic compact graph snapshot for record-level parity testing. owner: codex. Notes: this prepares the large-repo golden import/reference graph workflow.
- [x] 2026-06-18: Added compact Rust extraction for top-level Python globals and symbol-target import resolution for imported globals. owner: codex.
- [x] 2026-06-18: Made opt-in `CodebaseConfig(graph_backend="rust")` skip eager Python graph construction and expose compact `rust_*` record properties on `Codebase`. owner: codex. Notes: current checkout constructs 4.0x faster with 4.6x lower process max RSS than Python parse/object materialization while blocking lazy Python graph materialization.
- [x] 2026-06-18: Added lightweight Rust compact handles for Python `Codebase.files`, `symbols`, `classes`, `functions`, `global_vars`, `imports`, and basic `get_*` queries. owner: codex. Notes: current checkout constructs and exercises public read handles 5.3x faster with 4.6x lower process max RSS than Python parse/object materialization while keeping `CodebaseContext.nodes` blocked.
- [x] 2026-06-18: Added compact Python `ReferenceRecord` extraction for same-file and imported top-level symbol references inside top-level classes/functions. owner: codex. Notes: current checkout emits 3,666 compact references and remains 5.0x faster with 4.1x lower process max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added compact Python `DependencyRecord` construction from references. owner: codex. Notes: current checkout emits 2,020 de-duplicated dependency edges and remains 4.6x faster with 4.1x lower process max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added first pinned large-repo benchmark runner and Airflow baseline. owner: codex. Notes: Apache Airflow `2.10.5` at `b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf` matched 4,789 Python files and measured 6.218x faster wall time with 9.882x lower max RSS for the current compact Rust `Codebase` slice.
- [x] 2026-06-18: Added first pinned Airflow compact graph golden. owner: codex. Notes: committed stable hashes/samples for 4,789 files, 23,663 symbols, 40,580 imports, 19,011 import resolutions, 95,292 references, and 35,489 dependencies; the opt-in pytest wrapper can verify it against the pinned checkout.
- [x] 2026-06-18: Added nested Python function/method compact symbols and innermost reference source attribution. owner: codex. Notes: Airflow compact coverage now emits 52,339 symbols, 112,238 references, and 71,348 dependencies while staying 5.309x faster with 9.418x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added first local-binding shadow filter for compact Python references. owner: codex. Notes: parameters, local assignments, and nested definitions no longer resolve to imported/top-level symbols; Airflow compact graph now emits 105,739 references and 68,927 dependencies while staying 5.048x faster with 13.315x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added local-import shadow filtering for compact Python references. owner: codex. Notes: function-local imports no longer resolve later uses to imported/top-level symbols; Airflow compact graph now emits 105,624 references and 68,869 dependencies while staying 4.870x faster with 13.195x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added control-flow binding shadow filtering for compact Python references. owner: codex. Notes: `for`, `with ... as ...`, and `except ... as ...` targets no longer resolve later uses to imported/top-level symbols; Airflow compact graph now emits 105,467 references and 68,848 dependencies while staying 5.232x faster with 13.332x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added comprehension and match-pattern capture shadow filtering for compact Python references. owner: codex. Notes: this checkout now emits 4,089 compact references and 2,949 dependencies; pinned Airflow remained graph-stable at 105,467 references and 68,848 dependencies while staying 5.100x faster with 13.395x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added range-scoped lambda-parameter shadow filtering for compact Python references. owner: codex. Notes: lambda parameters now shadow only inside lambda bodies while default-value references still resolve outward; pinned Airflow stayed graph-stable at 105,467 references and 68,848 dependencies while staying 4.981x faster with 13.456x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added `global` declaration handling for compact Python references. owner: codex. Notes: `global` declarations no longer hide module-level symbols behind local assignment shadows; Airflow compact graph now emits 105,607 references and 68,917 dependencies while staying 4.987x faster with 13.393x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Skipped Python attribute field names as bare compact references. owner: codex. Notes: object-side references still resolve, but `obj.helper` no longer creates a false standalone `helper` dependency; Airflow compact graph now emits 104,622 references and 68,340 dependencies while staying 5.023x faster with 15.744x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Scoped comprehension target shadowing to comprehension expressions. owner: codex. Notes: prevents `[Base for Base in items]` from hiding later `Base` references in the enclosing function; Airflow compact graph stayed stable at 104,622 references and 68,340 dependencies while staying 4.899x faster with 15.745x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added imported module member references to the compact Rust graph. owner: codex. Notes: `module.some_func`, `alias.SomeClass`, and exact `pkg.module.some_func` qualifiers now resolve through existing import-resolution rows; Airflow compact graph now emits 109,282 references and 71,534 dependencies while staying 4.781x faster with 13.394x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added `nonlocal` declaration shadowing for compact Python references. owner: codex. Notes: `nonlocal helper` inside nested functions no longer creates a false imported/top-level `helper` reference; Airflow compact graph stayed stable at 109,282 references and 71,534 dependencies while staying 4.663x faster with 13.244x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added direct Python package re-export import resolution. owner: codex. Notes: `from pkg import Symbol` now follows matching imported bindings in `pkg/__init__.py`; Airflow compact graph now emits 109,655 references and 71,788 dependencies while staying 4.562x faster with 13.307x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added wildcard import/re-export chain resolution to the compact Rust graph. owner: codex. Notes: fixed-point exported-name tables now propagate `from module import *` across indexed internal modules; Airflow compact graph now emits 109,743 references and 71,863 dependencies while staying 4.806x faster with 13.136x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added nested module-prefix attribute resolution to the compact Rust graph. owner: codex. Notes: `from a import b; b.c.d()` and `import a.b; a.b.c.d()` now resolve through indexed internal module prefixes, including namespace-package-style prefixes without concrete `__init__.py` files; Airflow compact graph now emits 109,817 references and 71,932 dependencies while staying 4.374x faster with 12.940x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Added static `__all__` filtering for compact Python wildcard imports. owner: codex. Notes: literal `__all__ = ["Name"]` style assignments now restrict `from module import *` expansion without affecting explicit named imports; pinned Airflow stayed graph-stable at 109,817 references and 71,932 dependencies while staying 4.454x faster with 13.010x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Exposed compact Rust dependency and usage handles through the Python shell. owner: codex. Notes: compact symbols now answer `dependencies`, `usages`, and `symbol_usages` from Rust records, preparing pinned large-repo parity tests to assert graph APIs instead of only raw record dumps. Refreshed pinned Airflow benchmark: Rust `Codebase` is 4.675x faster with 13.099x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Exposed compact Rust import usage handles through the Python shell. owner: codex. Notes: compact imports now answer `usages` and `symbol_usages` from Rust references grouped by `import_id`, which lets parity tests assert import-graph consumers without materializing the Python graph. Refreshed pinned Airflow benchmark: Rust `Codebase` is 4.735x faster with 12.938x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Exposed compact Rust file inbound import handles through the Python shell. owner: codex. Notes: compact files now answer `inbound_imports` and `importers` from Rust import-resolution records, moving another P0 `SourceFile` graph query off the Python object graph. Refreshed pinned Airflow benchmark: Rust `Codebase` is 4.570x faster with 12.926x lower max RSS than Python parse/object materialization.
- [x] 2026-06-18: Exposed compact Rust file import lookup APIs through the Python shell. owner: codex. Notes: compact files now answer `import_statements`, `has_import`, and `get_import` from Rust import records, including alias/module/source lookup, moving another P0 `SourceFile` query off the Python object graph. Refreshed pinned Airflow benchmark: Rust `Codebase` is 4.570x faster with 12.981x lower max RSS than Python parse/object materialization.
