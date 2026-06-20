# Rust Rewrite Agent Handoff

Last updated: 2026-06-20

## Merge Posture

The `rust-rewrite` branch is intended to merge as the new baseline for continued development, with the Rust backend still treated as a compact backend that has explicit support boundaries. The Python backend is still present in this branch today, but the product direction is to remove it once the Rust backend can carry real applications without unacceptable correctness gaps.

Do not claim full parity yet. It is acceptable to merge if protected CI and the final local gates pass, because the backend is not currently serving production systems and the branch gives future agents a stronger foundation.

## Current Shape

- Python remains the public shell for now: `Codebase`, files, symbols, imports, transactions, and codemod execution still use the existing Python APIs.
- Rust owns compact indexing data for Python and TypeScript/JavaScript source files.
- The compact backend is optimized to avoid materializing the full Python graph for common large-repo queries.
- PyO3 exposes targeted JSON record queries so the Python shell can create small handle sets lazily.
- CI has fast checks, extension build checks, docs/site checks, wheel/uvx artifact checks, and large-repo opt-in checks.

## Final Pre-Merge Commands

Run these before merging if time allows:

```bash
uv run ruff check
cargo fmt --check
cargo test -p graph-sitter-engine --lib
uv run pytest tests/unit/sdk/codebase/test_rust_backend.py tests/unit/sdk/codebase/test_rust_rewrite_readiness.py -q
rust-rewrite/tools/check_fast.sh
```

If the machine has cached pinned repos and enough time, also run:

```bash
rust-rewrite/tools/check_pinned_large_repos.sh
```

Hosted checks on the current branch are the stronger merge signal for large-repo proof because they run in the same environment branch protection will see.

## What Is Supported Enough To Build On

- Compact codebase construction for Python and TypeScript.
- File/symbol/import/export read APIs listed in `rust-rewrite/supported-subset.json`.
- Targeted exact lookup paths that keep broad caches cold.
- Python and TypeScript codemod smoke flows for import edits, symbol rename, move-to-file, and transaction commit.
- Pinned Airflow and Next.js performance checks with large RSS improvements over recorded Python baselines.
- Read-only TypeScript function calls and Promise chains.
- Read-only TypeScript JSX element records:
  - `file.jsx_elements`
  - `symbol.jsx_elements`
  - `symbol.is_jsx`
  - nested `jsx_element.jsx_elements`

## Do Not Claim Yet

- Complete Python-vs-Rust graph parity.
- Complete TypeScript type-system/reference parity.
- Complete JSX prop or JSX mutation parity.
- Complete mutable expression object parity.
- Promise-chain async conversion parity.
- Rust backend readiness as a default backend for production without explicit rollout gates.

## High-Value Fanout Lanes

- Full graph parity harness: compare reference, import, dependency, and ordering graphs on pinned Airflow and Next.js commits.
- JSX mutation lane: add compact JSX prop records, prop value reads, `get_prop`, `add_prop`, `set_name`, and wrapper edits with parity tests.
- TypeScript type-system lane: broaden namespace/private/member semantics, interfaces, type aliases, enum references, and lexical scoping.
- Codemod expansion lane: run real codemods against pinned large repos and assert exact file-byte results plus latency/RSS.
- Default-backend/removal lane: define the sequence for making Rust default, then removing Python backend modules once parity gates prove acceptable coverage.
- Docs/distribution lane: keep `docs/`, `site/`, `uvx` docs, and skill packaging aligned with actual supported behavior.

## Multi-Agent Convention

Use `rust-rewrite/strategy.md` as the shared work ledger. Add checklist entries with this shape:

```markdown
- [ ] Short task title. owner: agent-name. Notes: exact scope and expected evidence.
- [x] Completed task title. owner: agent-name. Result: concrete files/tests/tools that prove it.
```

Keep each agent in a separate worktree. Integrator responsibilities:

- Pull each worktree branch.
- Review for support-boundary drift.
- Run focused tests for the touched surface.
- Update `supported-subset.json` and `p0-parity-coverage.json` when support changes.
- Reject claims that are not backed by tests, pinned reports, or direct command output.

## Useful Files

- `rust-rewrite/strategy.md`: shared checklist and implementation history.
- `rust-rewrite/supported-subset.json`: support contract validated by fast checks.
- `rust-rewrite/p0-parity-coverage.json`: P0 surface audit and open gaps.
- `rust-rewrite/benchmarks.md`: benchmark context and current numbers.
- `rust-rewrite/python-compat.md`: fallback and unsupported API behavior.
- `rust-rewrite/tools/check_fast.sh`: fast branch readiness gate.
- `rust-rewrite/tools/check_pinned_large_repos.sh`: expensive pinned proof gate.
