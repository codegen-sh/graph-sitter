# Rust Backend Reference

Use this before making Rust backend, performance, fallback, parity, or distribution claims.

## Backend Modes

Configure through `CodebaseConfig`:

```python
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode

CodebaseConfig(graph_backend=GraphBackend.PYTHON)
CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)
CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.PYTHON)
CodebaseConfig(graph_backend=GraphBackend.AUTO)
```

- `PYTHON` remains the default and primary compatibility backend.
- `RUST` is opt-in compact mode. In strict mode, supported APIs stay graph-free and unsupported APIs raise `RustBackendUnsupportedError`.
- `rust_fallback=PYTHON` is a compatibility escape hatch; unsupported methods may promote to the Python graph.
- `AUTO` is reserved for gradual rollout when language coverage and packaging are stable enough.

## Current Distribution Status

Local Rust mode requires the PyO3 extension to be built and importable. Wheels built from the rust-rewrite branch now bundle the top-level `graph_sitter_py` module, and the distribution proof is:

```bash
rust-rewrite/tools/check_wheel_rust_backend.sh
```

Use `--backend python` in published-package examples until a release ships these wheels. Use `uvx --from dist/<wheel>.whl graph-sitter parse ... --backend rust --fallback error` for branch-built wheel validation.

## Supported Claims

Use careful wording:

- "supported Rust-backend subset"
- "selected pinned large-repo semantic parity"
- "selected Airflow and Next.js readiness proofs"
- "Python backend remains default until rollout gates and published-package validation pass"

Avoid these claims:

- absolute semantic correctness
- complete graph-wide parity
- Rust backend is ready as the default
- `uvx --backend rust` works from PyPI before a release ships the Rust-backed wheels

## Local Validation Gates

Fast branch validation:

```bash
rust-rewrite/tools/check_fast.sh
```

Large-repo validation when Rust backend behavior or performance claims change:

```bash
rust-rewrite/tools/check_pinned_large_repos.sh
```

Targeted proof tools include:

- `rust-rewrite/tools/check_supported_subset.py`
- `rust-rewrite/tools/check_p0_parity_coverage.py`
- `rust-rewrite/tools/check_python_rust_parity_fixture.py`
- `rust-rewrite/tools/check_pinned_semantic_parity.py`

Only run the large pinned checks when needed; they are heavier than the skill prototype validation.
