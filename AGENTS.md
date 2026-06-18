# AGENTS.md

## What This Is

Graph-sitter is a Python SDK and `gs` CLI for analyzing and transforming codebases. It builds a graph over files, symbols, imports, references, and dependencies so codemods can edit Python, TypeScript, JavaScript, and React projects without hand-rolling AST traversal or import bookkeeping.

Use `from graph_sitter import Codebase` as the primary entrypoint. Most work is: load a `Codebase`, find symbols/files/imports, call edit helpers such as move, rename, docstring, type, or import methods, then commit or run through the CLI.

## Repo Map

- `src/graph_sitter/core`: language-agnostic symbols, statements, expressions, and edit APIs.
- `src/graph_sitter/python` and `src/graph_sitter/typescript`: language-specific implementations.
- `src/graph_sitter/codebase`: `Codebase` construction, sessions, graph state, and IO.
- `src/graph_sitter/cli`: user-facing `gs` commands for init/create/run/notebook/MCP.
- `src/graph_sitter/runner` and `src/graph_sitter/git`: running codemods, diffs, PR/git integration.
- `src/codemods`: bundled canonical and misc codemods.
- `docs`: Mintlify docs. `examples`: runnable example codemods and demos.
- `tests/unit`: focused API tests. `tests/integration/codemod`: larger codemod behavior tests.

## Setup

```bash
uv venv
source .venv/bin/activate
uv sync --dev
```

Python support is `>=3.12,<3.14`; Python 3.13 is preferred. If compiled extensions look stale, try `uv sync --reinstall-package graph-sitter`.

## Checks

```bash
uv run pytest tests/unit -n auto
uv run pytest tests/integration/codemod/test_codemods.py -n auto
```

For narrow changes, run the closest test file first, then one of the broader commands above when the edit affects shared APIs, parsing, graph behavior, or codemod execution.

## Agent Notes

- Prefer existing graph/edit APIs over string edits. Keep transformations semantic and let Graph-sitter manage imports/references where possible.
- Preserve language-specific boundaries: core abstractions belong in `core`, Python behavior in `python`, TypeScript/JS behavior in `typescript`.
- Keep generated or embedded prompt/docs changes scoped; `src/graph_sitter/cli/mcp/resources/system_prompt.py` is large generated-style context.
- Read nearby README files before changing examples, docs, CLI, runner, or git integration.
- Do not broaden codemod behavior without adding or updating codemod integration coverage.
