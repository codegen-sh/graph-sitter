# Rust Backend Reference

Use this before making Rust backend, TypeScript large-repo, fallback, performance, memory, parity, wheel, or release claims.

## Backend Modes

Configure the Python API through `CodebaseConfig`:

```python
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode

CodebaseConfig(graph_backend=GraphBackend.PYTHON)
CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR)
CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.PYTHON)
CodebaseConfig(graph_backend=GraphBackend.AUTO)
```

CLI equivalents:

```bash
uvx graph-sitter parse /repo --backend python
uvx graph-sitter parse /repo --backend rust --fallback error
uvx graph-sitter diagnose /repo --backend auto --fallback python --json
```

## Claims To Make

Use precise language:

- "supported Rust-backend subset"
- "selected pinned large-repo parity"
- "Rust-backed parse/diagnose on this package/platform"
- "Python backend remains the compatibility backend"

Avoid overclaims:

- complete graph-wide parity
- absolute semantic correctness
- Rust backend is always the default
- Rust-backed `uvx` works from PyPI before release validation proves it

## Validation

Check installation and strict Rust readiness:

```bash
uvx graph-sitter doctor --backend rust --language python --json
uvx graph-sitter doctor --backend rust --language typescript --json
```

Measure parse time and memory:

```bash
uvx graph-sitter diagnose /repo --language typescript --backend rust --fallback error --json
```

For local Graph-sitter source work, use repository gates when Rust backend behavior changes:

```bash
rust-rewrite/tools/check_fast.sh
rust-rewrite/tools/check_pinned_large_repos.sh
```

Run large pinned checks only when the change touches Rust backend behavior, performance claims, packaging, or large-repo parsing.

## Large Repos

Prefer Rust for broad TypeScript and monorepo discovery when strict support is available:

```bash
uvx graph-sitter parse /repo --language typescript --backend rust --fallback error --format json
uvx graph-sitter callgraph packages/app/src/index.ts.main /repo --language typescript --backend rust --depth 2
```

Prefer scoped Python queries when inbound call-site detail or unsupported semantic surfaces are required:

```bash
uvx graph-sitter usages packages/app/src/index.ts.main /repo --language typescript --backend python --subdir packages/app --depth 2
```

When reporting performance, include repo path or commit, platform, Python version, package source, backend, fallback mode, wall time, peak RSS, and whether broad JSON output or Python graph materialization was requested.
