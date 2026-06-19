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

## Current Distribution Limitation

Local Rust mode requires the PyO3 extension to be built and importable. `uvx graph-sitter ... --backend rust` cannot be promised to users until release wheels bundle the extension. Until then, use `--backend python` in distributed CLI examples, or explain the local extension build prerequisite.

## Supported Claims

Use careful wording:

- "supported Rust-backend subset"
- "selected pinned large-repo semantic parity"
- "selected Airflow and Next.js readiness proofs"
- "Python backend remains default until rollout gates and packaging pass"

Avoid these claims:

- absolute semantic correctness
- complete graph-wide parity
- Rust backend is ready as the default
- `uvx --backend rust` works from published wheels

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
