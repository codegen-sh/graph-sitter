# CLI Reference

Use this reference when the task can be handled through `graph-sitter` commands rather than custom Python.

## Invocation

Use the released package with `uvx`:

```bash
uvx graph-sitter --help
uvx graph-sitter COMMAND --help
```

Use the local source checkout with `uv run`:

```bash
uv run graph-sitter --help
uv run graph-sitter COMMAND --help
```

`graph-sitter` is the canonical command. `gs` is a compatibility alias.

## Install And Skill Distribution

Install this skill through the skills CLI, not `uvx`:

```bash
npx skills add codegen-sh/graph-sitter
```

Use `uvx` to run the Graph-sitter Python package:

```bash
uvx graph-sitter parse /path/to/repo --format json
```

## Shared Parse Options

Most graph commands accept:

- `--backend python|rust|auto`: choose the graph backend.
- `--fallback python|error`: control behavior when Rust is unavailable or unsupported.
- `--language auto|python|typescript`: choose language detection explicitly.
- `--subdir PATH`: limit parsing to a repo-relative file or directory; repeat it for multiple scopes.
- `--format summary|json`: choose human-readable or machine-readable output.

Prefer `--subdir` for monorepos when the user asks about a package, service, or file cluster.

## Parse And Diagnose

Use `parse` for count summaries and machine-readable graph size signals:

```bash
uvx graph-sitter parse /repo --language auto --backend python --format json
uvx graph-sitter parse /repo --language typescript --backend rust --fallback error --format json
uvx graph-sitter parse /repo --subdir packages/app --format json
```

Use `diagnose` when wall time, memory, parse errors, or backend behavior matters:

```bash
uvx graph-sitter diagnose /repo --language auto --backend auto --fallback python --json
uvx graph-sitter diagnose /repo --language typescript --backend rust --fallback error --json
```

Use `doctor` for installation readiness:

```bash
uvx graph-sitter doctor --json
uvx graph-sitter doctor --backend rust --language python --json
uvx graph-sitter doctor --backend rust --language typescript --json
```

## Inspect Files

Use `inspect` for source-file structure, line numbers, and per-function call summaries:

```bash
uvx graph-sitter inspect src/app.py /repo --level summary
uvx graph-sitter inspect src/app.py /repo --level functions
uvx graph-sitter inspect src/app.py /repo --level calls
uvx graph-sitter inspect src/app.py /repo --level full --format json
```

Useful limits:

- `--max-functions N`: cap function records.
- `--max-calls N`: cap per-function call names.

## Resolve Targets

Start with `symbols` when a target is not exact:

```bash
uvx graph-sitter symbols runInference /repo --kind function
uvx graph-sitter symbols AuthService /repo --kind class --format json
```

Use target strings printed by `symbols`. Supported forms include:

- `qualifiedName` when globally unique.
- `path/to/file.py:function_name`.
- `path/to/file.py::function_name`.
- `path/to/file.py.function_name`.
- `path/to/file.py.ClassName.method_name`.

If Graph-sitter reports ambiguity, rerun `symbols` with a narrower query or add the file path.

## Trace Calls

Use `using` for outbound callees:

```bash
uvx graph-sitter using src/app.py.handler /repo --depth 2 --resolved-only --local-only --dedupe
```

Use `usages` for inbound callers and usage sites:

```bash
uvx graph-sitter usages src/app.py.helper /repo --depth 2 --resolved-only --local-only --dedupe
```

Use `callgraph` for a clean first-party trace; it defaults to resolved, local, deduped edges unless `--raw` is passed:

```bash
uvx graph-sitter callgraph src/app.py.handler /repo --direction outbound --depth 3
uvx graph-sitter callgraph src/app.py.helper /repo --direction inbound --depth 2
```

Filtering options for `using` and `usages`:

- `--resolved-only`: drop unresolved calls.
- `--local-only`: keep only parsed local files on both sides.
- `--hide-runtime`: suppress common runtime/library helpers.
- `--dedupe`: collapse repeated source/target/call triples.

## Rename

Run check mode first:

```bash
uvx graph-sitter rename src/app.py.helper /repo --to execute_helper --check --format json
```

Apply only after reviewing the target, counts, and affected files:

```bash
uvx graph-sitter rename src/app.py.helper /repo --to execute_helper --write
```

Follow with `git diff` and focused tests.
