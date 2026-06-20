# Future Agent Brief

Last updated: 2026-06-20

This branch is intended to become the new development baseline, not the final Rust-only product. Treat the merge as a staging point that lets many agents fan out from one shared Rust compact backend.

## Current Merge Stance

- PR baseline: `rust-rewrite` into `develop`.
- Public API stance: keep the Python shell for users and codemods.
- Backend stance: Rust compact mode is opt-in and covers the supported subset documented in `supported-subset.json`.
- Python backend stance: keep it after this merge. Delete it only after the deletion gates below pass.
- CI stance: fast Rust checks, extension builds, wheel smokes, docs/site checks, and large-repo opt-in checks are the meaningful signal for this baseline. Branch-wide mypy is intentionally skipped for the baseline PR because the branch carries known type debt across a large changed Python surface. The legacy `integration-tests` job is also skipped only for the `rust-rewrite` baseline PR because it pushes branches to an external GitHub fixture repo and requires a writable PAT; restore or replace that lane after merge.

## What Future Agents Should Trust

- `CodebaseConfig(graph_backend="rust", rust_fallback="error")` is the strict proof path.
- Strict Rust mode must not materialize `CodebaseContext.nodes`.
- Supported APIs are listed in `rust-rewrite/supported-subset.json` and are validated by `rust-rewrite/tools/check_fast.sh`.
- P0 parity groups and known open gaps are listed in `rust-rewrite/p0-parity-coverage.json`.
- Pinned large-repo proof uses Airflow `2.10.5` and Next.js `v15.0.0`.
- Codemod proof exists for Python and TypeScript import/rename/move flows, including installed-wheel `uvx --from dist/<wheel>.whl graph-sitter ...` smoke paths.

## Do Not Trust Yet

- Full graph-wide semantic parity on arbitrary large repositories.
- Full TypeScript type-system, namespace, JSX prop, and mutable expression-object parity.
- Python backend deletion readiness.
- Published-package `uvx graph-sitter ...` claims until a real released artifact is validated.
- Branch-wide mypy cleanliness.
- Legacy GitHub push integration coverage on the baseline PR; the Rust merge signal comes from unit, fast, extension, wheel, docs/site, and large-repo proof lanes.

## Python Backend Deletion Gates

The Python backend can be removed only after these are complete:

- [ ] Make Rust the default backend behind an explicit release note and rollout flag. Evidence: protected CI plus default-backend tests prove normal `Codebase(...)` construction selects Rust for supported Python and TypeScript repos.
- [ ] Keep Python fallback for one release after the default flip. Evidence: release notes, fallback tests, and telemetry or user feedback window.
- [ ] Close `p0-parity-coverage.json` with `check_p0_parity_coverage.py --require-complete`. Evidence: no open P0 groups.
- [ ] Add full graph-wide parity harnesses for pinned Airflow and Next.js. Evidence: file, import, export, reference, dependency, external-reference, subclass, and deterministic ordering comparisons.
- [ ] Expand codemod parity beyond smoke flows. Evidence: real codemods on pinned large repos assert exact file-byte diffs, changed-file sets, wall time, and RSS.
- [ ] Replace or remove Python-only graph internals. Evidence: no required public path depends on `rustworkx.PyDiGraph`, eager `SourceFile._nodes`, persistent `tree_sitter.Node` wrappers, or Python object graph traversal.
- [ ] Restore normal mypy and external integration expectations. Evidence: remove the `rust-rewrite` PR skip in `.github/workflows/mypy.yml`, remove the baseline-only `integration-tests` skip in `.github/workflows/test.yml`, or replace the fixture-push tests with hermetic/local equivalents.
- [ ] Validate released `uvx graph-sitter ...` package behavior. Evidence: `uvx graph-sitter doctor`, `parse`, `run`, and `transform` work from a clean environment with a published version.

## Highest-Value Fanout Work

- [ ] Full parity harness agent. Build repo-wide Python-vs-Rust graph equality tools for pinned Airflow and Next.js.
- [ ] TypeScript correctness agent. Close type/interface/namespace/private/member gaps and add focused fixtures before touching large repos.
- [ ] JSX codemod agent. Add compact JSX prop records, prop reads, prop mutation, wrapper edits, and exact mutation parity tests.
- [ ] Codemod scale agent. Run real codemods against pinned large repos and assert exact diffs plus latency/RSS.
- [ ] CI debt agent. Keep fast PR checks under a few minutes, move expensive checks to scheduled/manual lanes, and restore type checking.
- [ ] Docs/release agent. Keep the Next.js docs site, Vercel deployment notes, `uvx` docs, and skill packaging aligned with what is actually tested.
- [ ] Deletion planning agent. Inventory every Python backend module, classify keep/replace/delete, and produce a stepwise removal PR plan.

## Integrator Rules

- Work in separate worktrees and branches.
- Add or update a checkbox in `rust-rewrite/strategy.md` for every non-trivial task.
- Do not expand `supported-subset.json` without tests.
- Do not close a P0 gap without adding evidence to `p0-parity-coverage.json`.
- Do not weaken pinned benchmark thresholds without recording the runner reason and preserving correctness gates.
- Keep docs conservative. Say "supported subset" or "strict Rust mode" unless a release artifact and parity gate prove the broader claim.

## Useful Commands

```bash
uv run ruff check
cargo fmt --check
cargo test -p graph-sitter-engine --lib
cargo test -p graph-sitter-py --lib
uv run pytest tests/unit/sdk/codebase/test_rust_backend.py tests/unit/sdk/codebase/test_rust_rewrite_readiness.py -q
rust-rewrite/tools/check_fast.sh
```

Expensive proof path:

```bash
rust-rewrite/tools/check_pinned_large_repos.sh
```
