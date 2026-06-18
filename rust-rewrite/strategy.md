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
- [ ] Measure cold parse RSS and wall time for canonical small, medium, and huge repos.
- [ ] Measure graph node/edge counts, Python object counts, and per-phase allocation peaks.
- [x] Document the exact current build phases with timings: file enumeration, parse, directory tree, config parse, import resolution, export resolution, dependency recompute. owner: Poincare. Result: added phase map in `rust-rewrite/benchmarks.md`; representative repo timings remain open.
- [x] Inventory all public `Codebase` properties and methods. owner: Dewey. Result: documented in `rust-rewrite/api-inventory.md`.
- [x] Inventory all public `SourceFile`, `Symbol`, `Import`, `Export`, and `Directory` APIs used by tests/docs. owner: Dewey. Result: documented in `rust-rewrite/api-inventory.md`.
- [x] Define P0 compatibility surface for the first Rust backend slice. owner: Dewey. Result: documented in `rust-rewrite/api-inventory.md`.
- [ ] Define large-repo success targets for memory and time.
- [ ] Select pinned large Python repo commits for golden parity and latency benchmarks. Notes: Airflow is a good first candidate.
- [ ] Build golden reference/import/dependency graph snapshots for the pinned large Python repo commits.
- [x] Draft compact Rust data model with module boundaries and Python integration points. owner: Pasteur. Result: documented in `rust-rewrite/data-model.md`.
- [ ] Draft full Rust engine RFC with module boundaries and Python integration points.
- [ ] Decide build tooling: `maturin`, setuptools-rust, or hatch custom hook.

## Phase 1: Rust Engine Skeleton

- [x] Add Rust workspace/crate skeleton without changing default behavior. owner: Beauvoir. Result: added standalone Cargo workspace under `crates/`.
- [x] Add PyO3 module import smoke test. owner: codex. Result: built the extension module and imported it from Python, then indexed this repo through `index_python_path`.
- [x] Add `graph_backend` config flag with default `python`. owner: codex. Result: added `GraphBackend` and `RustFallbackMode` to `CodebaseConfig`.
- [x] Add compact Rust index facade that can be constructed from `CodebaseContext`. owner: codex. Result: `ctx.rust_index` builds through the optional PyO3 extension when `graph_backend` is `rust` or `auto`.
- [ ] Add full Rust engine facade object that can back existing `CodebaseContext` graph query APIs.
- [x] Add a minimal debug API returning engine version and enabled features. owner: Beauvoir. Result: added Rust `Engine::debug_info` and feature-gated PyO3 bindings.
- [ ] Add CI job that builds the Rust extension on supported Python versions.
- [x] Add benchmark command comparing Python backend with Rust compact indexer. owner: codex. Result: added `rust-rewrite/tools/compare_rust_python_index.py`.
- [x] Add benchmark command for the Python-facing Rust facade. owner: codex. Result: added `rust-rewrite/tools/measure_rust_facade.py`.
- [ ] Add benchmark command that can select full `Codebase` `--backend python|rust` once Rust backend is wired into Python.

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
- [ ] Implement symbol usage extraction by identifier ranges.
- [ ] Implement dependency edge construction from usage records.
- [ ] Implement superclass/interface dependency edges.
- [ ] Add graph debug dump for nodes, edges, and usage metadata.
- [ ] Add parity tests comparing Python backend and Rust backend graph edges on fixtures.

## Phase 4: Lazy Python Compatibility Layer

- [x] Plan Python/PyO3 compatibility layer and lazy handle migration. owner: Wegener. Result: documented in `rust-rewrite/python-compat.md`.
- [ ] Define Python handle base class that stores engine reference and stable ID.
- [ ] Implement Rust-backed file handles for P0 `SourceFile` APIs.
- [ ] Implement Rust-backed symbol handles for P0 `Symbol`, `Class`, and `Function` APIs.
- [ ] Implement Rust-backed import handles for P0 `Import` APIs.
- [ ] Implement Rust-backed export handles for P0 TypeScript `Export` APIs.
- [ ] Make `Codebase.files` return lazy handles under Rust backend.
- [ ] Make `Codebase.symbols`, `classes`, `functions`, `imports`, and `exports` return lazy handles under Rust backend.
- [ ] Preserve existing sorting behavior for public query results.
- [ ] Add fallback path to Python backend for unsupported methods.
- [ ] Add tests that verify no full Python object graph is materialized for simple list queries.

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
- [ ] Add pinned large-repo parity test for reference graph, import graph, dependency graph, and latency/RSS.
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
