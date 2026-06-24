---
name: graph-sitter
description: Use Graph-sitter to inspect, query, and transform Python, TypeScript, JavaScript, and React repositories through `uvx graph-sitter` or the local Python API. Trigger when Codex needs semantic codebase graphs, symbol discovery, call graph or usage tracing, import/dependency analysis, graph-aware renames, codemod execution, large-repo parse diagnostics, or safe structural edits.
---

# Graph-sitter

Graph-sitter is the codebase graph and codemod layer. Use it when ordinary text search is too weak: find exact symbols first, inspect file structure, trace inbound or outbound calls, then perform graph-aware transformations only after check-mode validation.

## Load References

- Read `references/cli.md` when using `graph-sitter`, `uvx graph-sitter`, `parse`, `diagnose`, `inspect`, `symbols`, `callgraph`, `using`, `usages`, or `rename`.
- Read `references/codemods.md` before writing or running a codemod, `transform`, `run`, or any command that may change files.
- Read `references/rust-backend.md` before making Rust backend, fallback, TypeScript large-repo, performance, memory, parity, wheel, or release claims.

## Choose The Interface

1. Use `uvx graph-sitter ...` for released package workflows and one-shot use outside the Graph-sitter checkout.
1. Use `uv run graph-sitter ...` when working inside a local Graph-sitter source checkout.
1. Use the Python API when the task needs custom traversal, filtering, or codemod logic beyond a built-in CLI command.
1. Use ordinary `rg`, editor inspection, and project tests alongside Graph-sitter; do not replace cheap local evidence with a graph query when text search is enough.

There is no `uvx` equivalent for installing skills from `skills.sh`; use `npx skills add ...` for skill installation and `uvx graph-sitter ...` for running the Python package.

## Core Workflow

1. Start with repository state:

   ```bash
   git status --short
   uvx graph-sitter doctor --json
   ```

1. Parse or diagnose before deeper graph queries:

   ```bash
   uvx graph-sitter parse /path/to/repo --language auto --backend python --format json
   uvx graph-sitter diagnose /path/to/repo --language auto --backend auto --fallback python --json
   ```

1. Find exact targets before tracing or renaming:

   ```bash
   uvx graph-sitter symbols runInference /path/to/repo --kind function
   ```

1. Use copyable target strings from `symbols`. Targets may be globally unique names, `path/to/file.py:handler`, `path/to/file.py::handler`, or dotted file targets such as `src/app.py.handler`.

1. Prefer scoped parsing on large monorepos:

   ```bash
   uvx graph-sitter inspect packages/app/src/index.ts /repo --subdir packages/app --level calls
   uvx graph-sitter usages packages/app/src/index.ts.main /repo --subdir packages/app --depth 2 --resolved-only --local-only --dedupe
   ```

## Common Tasks

Use `inspect` for a file summary:

```bash
uvx graph-sitter inspect src/app.py /repo --level functions
uvx graph-sitter inspect packages/app/src/index.ts /repo --level full --format json
```

Use `using`, `usages`, or `callgraph` for structure:

```bash
uvx graph-sitter using src/app.py.handler /repo --depth 2 --resolved-only --local-only --dedupe
uvx graph-sitter usages src/app.py.helper /repo --depth 2 --resolved-only --local-only --dedupe
uvx graph-sitter callgraph src/app.py.handler /repo --direction outbound --depth 3
uvx graph-sitter callgraph src/app.py.handler /repo --direction inbound --depth 2
```

Use `rename` only after check mode:

```bash
uvx graph-sitter rename src/app.py.helper /repo --to execute_helper --check
uvx graph-sitter rename src/app.py.helper /repo --to execute_helper --write
```

Use `transform` for ad hoc codemods and `run` for registered workspace codemods. Always run `--check` before `--write`.

```bash
uvx graph-sitter transform ./codemod.py:run /repo --check
uvx graph-sitter run rename-symbol /repo --check
```

## Python API

Use the Python API for custom analysis:

```python
from graph_sitter import Codebase

codebase = Codebase("/path/to/repo")
source_file = codebase.get_file("src/app.py")
handler = source_file.get_function("handler")
print([dependency.name for dependency in handler.dependencies])
```

Prefer targeted file and symbol lookups over broad graph materialization in large repos.

## Safety Rules

- Run `git status --short` before any mutation.
- Use `--format json` when downstream parsing matters.
- Use `--check` before `--write` for `rename`, `transform`, and `run`.
- Inspect `git diff` after a write, then run focused tests or type checks for touched code.
- Keep Rust-backend claims scoped to the supported subset and validated package/platform.
