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

- [ ] Benchmarks/profiling. owner: Poincare. Agent: `019edc37-802c-7223-8d37-75a51b65abbd`. Branch: `codex/rust-rewrite-benchmarks`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-benchmarks`.
- [ ] API inventory. owner: Dewey. Agent: `019edc37-82ff-7b92-9fac-5364e2d8098b`. Branch: `codex/rust-rewrite-api-inventory`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-api-inventory`.
- [ ] Rust data model. owner: Pasteur. Agent: `019edc37-859c-71b2-b884-ab7a2bfc707e`. Branch: `codex/rust-rewrite-data-model`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-data-model`.
- [ ] Parser/index vertical slice. owner: Meitner. Agent: `019edc37-8867-7a83-a18e-b0ec0ca29d11`. Branch: `codex/rust-rewrite-parser-index`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-parser-index`.
- [ ] Resolver/dependency algorithms. owner: Gauss. Agent: `019edc37-8c34-7f93-b0ae-746cbd579962`. Branch: `codex/rust-rewrite-resolver`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-resolver`.
- [ ] Rust engine skeleton. owner: Beauvoir. Agent: `019edc37-8f2d-7dd3-b3ed-a1f9e1b191a7`. Branch: `codex/rust-rewrite-engine-skeleton`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-engine-skeleton`.
- [ ] PyO3/Python compatibility. owner: queued. Branch: `codex/rust-rewrite-pyo3-compat`. Worktree: `/Users/jayhack/CS/CODEGEN/graph-sitter-rust-pyo3-compat`. Notes: agent spawn queued until an active helper completes.

## Phase 0: Baseline, RFC, And Contracts

- [ ] Add memory benchmark harness for current Python backend.
- [ ] Measure cold parse RSS and wall time for representative repos.
- [ ] Measure graph node/edge counts, Python object counts, and per-phase allocation peaks.
- [ ] Document the exact current build phases with timings: file enumeration, parse, directory tree, config parse, import resolution, export resolution, dependency recompute.
- [ ] Inventory all public `Codebase` properties and methods.
- [ ] Inventory all public `SourceFile`, `Symbol`, `Import`, `Export`, and `Directory` APIs used by tests/docs.
- [ ] Define P0 compatibility surface for the first Rust backend slice.
- [ ] Define large-repo success targets for memory and time.
- [ ] Draft Rust engine RFC with module boundaries and Python integration points.
- [ ] Decide build tooling: `maturin`, setuptools-rust, or hatch custom hook.

## Phase 1: Rust Engine Skeleton

- [ ] Add Rust workspace/crate skeleton without changing default behavior.
- [ ] Add PyO3 module import smoke test.
- [ ] Add `graph_backend` config flag with default `python`.
- [ ] Add Rust engine facade object that can be constructed from `CodebaseContext`.
- [ ] Add a minimal debug API returning engine version and enabled features.
- [ ] Add CI job that builds the Rust extension on supported Python versions.
- [ ] Add benchmark command that can select `--backend python|rust`.

## Phase 2: Parser And Compact Index Vertical Slice

- [ ] Implement Rust file discovery input format from Python repo operator.
- [ ] Implement tree-sitter parser setup for Python.
- [ ] Implement tree-sitter parser setup for TypeScript/TSX.
- [ ] Extract file records with path, language, content hash, and root ranges.
- [ ] Extract top-level Python classes, functions, and globals.
- [ ] Extract top-level TypeScript classes, functions, interfaces, type aliases, enums, and globals.
- [ ] Extract imports for Python.
- [ ] Extract imports and exports for TypeScript.
- [ ] Build path and string interners.
- [ ] Expose `files`, `symbols`, `classes`, `functions`, `imports`, and `exports` ID queries through PyO3.
- [ ] Add golden snapshots for compact IR on small Python fixtures.
- [ ] Add golden snapshots for compact IR on small TypeScript fixtures.

## Phase 3: Resolution And Dependency Graph

- [ ] Port Python import resolution rules.
- [ ] Port TypeScript relative import resolution rules.
- [ ] Port TypeScript config/path alias handling.
- [ ] Represent external modules compactly.
- [ ] Implement import-to-file and import-to-symbol edges.
- [ ] Implement export-to-symbol/import/file edges.
- [ ] Implement lexical scope tables for name resolution.
- [ ] Implement symbol usage extraction by identifier ranges.
- [ ] Implement dependency edge construction from usage records.
- [ ] Implement superclass/interface dependency edges.
- [ ] Add graph debug dump for nodes, edges, and usage metadata.
- [ ] Add parity tests comparing Python backend and Rust backend graph edges on fixtures.

## Phase 4: Lazy Python Compatibility Layer

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

- [ ] 2026-06-18: Initial strategy file created on `rust-rewrite` branch. owner: codex. Notes: ready for helper agents to claim phase tasks.
- [ ] 2026-06-18: Integrator created seven worktrees and spawned six helper agents; PyO3 compatibility is queued due to agent concurrency limit. owner: codex.
