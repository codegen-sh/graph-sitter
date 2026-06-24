# Codemod Reference

Use this before writing or running Graph-sitter transformations.

## Import-Path Transform

Create a Python module with a function that accepts `codebase`:

```python
def run(codebase):
    source_file = codebase.get_file("src/app.py")
    target = source_file.get_function("old_name")
    target.rename("new_name")
    codebase.commit()
```

Preview first:

```bash
uvx graph-sitter transform ./codemod.py:run /repo --check --diff-preview 200
```

Apply only after reviewing the diff:

```bash
uvx graph-sitter transform ./codemod.py:run /repo --write
```

The transform loader also accepts `Codemod` subclasses or instances with `execute(codebase)`.

## Arguments

Pass JSON to transforms that accept an `arguments` parameter:

```bash
uvx graph-sitter transform ./codemod.py:run /repo --arguments '{"old":"foo","new":"bar"}' --check
```

Prefer explicit Pydantic argument models in reusable codemods so invalid inputs fail early.

## Registered Workspace Codemods

Use `run` when the repository already has registered `.codegen/codemods` functions:

```bash
uvx graph-sitter run rename-symbol /repo --check --arguments '{"name":"new_name"}'
uvx graph-sitter run rename-symbol /repo --write --arguments '{"name":"new_name"}'
```

`run` still writes by default for compatibility. Always pass `--check` or `--write` explicitly in agent workflows.

## Safety Workflow

1. Inspect `git status --short` before running the codemod.
1. Run with `--check` and review the diff.
1. Use `--write` only when the diff matches the requested change.
1. Inspect `git diff` after writing.
1. Run focused tests, type checks, or linters for touched files.

For ordinary user codemods, call `codebase.commit()` after edits. Use stricter commit options only when the repository already documents that pattern or the task explicitly needs compact Rust-backend mutation proof.
