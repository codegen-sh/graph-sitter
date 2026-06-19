---
name: graph-sitter
description: Use Graph-sitter to parse, query, analyze, and transform Python, TypeScript, JavaScript, and React codebases. Trigger when Codex needs codebase graph APIs, dependency/import/reference/usage analysis, codemod execution, large-repo Rust-backed parsing status, or `uvx graph-sitter ...` / local `graph-sitter` CLI workflows.
---

# Graph-sitter

Use Graph-sitter as the codebase graph and codemod layer. Prefer the Python API for custom analysis and transformations; use the CLI for simple parse summaries, repeatable codemod runs, and import-path transforms.

## Load References

- Read `references/cli.md` when using `graph-sitter`, `uvx graph-sitter`, `parse`, `run`, or `transform`.
- Read `references/codemods.md` before writing or running a codemod.
- Read `references/rust-backend.md` before making Rust backend, performance, parity, fallback, or wheel-distribution claims.

## Choose The Path

1. For read-only inspection, start with `Codebase` in Python unless a JSON CLI summary is enough.
2. For one-shot command-line summaries, run `graph-sitter parse` locally from the checkout with `uv run`, or use `uvx graph-sitter parse` only when the package is installed or supplied with `uvx --from`.
3. For transformations, prefer `graph-sitter transform MODULE:OBJECT PATH --check` before `--write` when the transform is not already registered under `.codegen/codemods`.
4. For large repositories, avoid broad list materialization unless the user asks for it. Prefer targeted lookups such as `get_file`, `get_function`, `get_import`, `find_by_byte_range`, dependencies, and usage probes.
5. For unsupported Graph-sitter surfaces, fall back to ordinary code inspection or the Python backend. Do not imply the Rust backend has complete semantic coverage.

## Python API

Use the Python shell as the primary interface for custom work:

```python
from graph_sitter import Codebase

codebase = Codebase("/path/to/repo")
file = codebase.get_file("src/app.py")
symbol = file.get_function("main")
print([dep.name for dep in symbol.dependencies])
```

For strict local Rust-backend checks, import config enums from their current module:

```python
from graph_sitter import Codebase
from graph_sitter.configs.models.codebase import CodebaseConfig, GraphBackend, RustFallbackMode

codebase = Codebase(
    "/path/to/repo",
    config=CodebaseConfig(
        graph_backend=GraphBackend.RUST,
        rust_fallback=RustFallbackMode.ERROR,
    ),
)
```

Use strict Rust mode only when the PyO3 extension is built in the local environment and the task stays inside the supported subset. The Python backend remains the default and the primary compatibility shell.

## CLI Shortcuts

For local source checkouts:

```bash
uv run graph-sitter parse /path/to/repo --backend python --format json
uv run graph-sitter transform ./codemod.py:run /path/to/repo --check
```

For distributed or installed package flows:

```bash
uvx graph-sitter parse /path/to/repo --backend python --format json
uvx --from dist/<wheel>.whl graph-sitter parse /path/to/repo --backend rust --fallback error --format json
uvx graph-sitter transform ./codemod.py:run /path/to/repo --check
```

The `parse` command and `transform MODULE:OBJECT` surface are implemented locally in the rust-rewrite branch. Rust backend execution from wheels built on this branch is supported by the wheel smoke; published-package availability still depends on release.

## Correctness And Claims

- Say "supported Rust-backend subset" or "selected pinned large-repo parity" when summarizing Rust status.
- Do not claim absolute semantic correctness or graph-wide parity.
- Current large-repo proofs cover selected Airflow and Next.js paths, supported-subset tests, and readiness gates. Use the local validation tools before making stronger claims.
- When measuring performance, record backend, command, repo/ref, wall time, max RSS, and whether broad Python-side caches were materialized.

## Validation

For Graph-sitter work, validate the exact thing changed:

```bash
uv run graph-sitter parse /path/to/repo --backend python --format json
uv run graph-sitter transform ./codemod.py:run /path/to/repo --check
git diff -- /path/to/repo
```

For Rust-backend branch validation, prefer the repository gates documented in `references/rust-backend.md`; do not use pinned large-repo checks unless the user asks or the change touches Rust backend behavior.

When maintaining this skill artifact, run the Codex skill validator against the `graph-sitter` skill folder before distribution.
