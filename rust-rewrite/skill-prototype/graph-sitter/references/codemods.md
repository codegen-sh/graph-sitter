# Codemod Reference

Use this before writing or running transformations.

## Import-Path Transform

Create a small module with a function that accepts `codebase`:

```python
def run(codebase):
    target = codebase.get_function("old_name")
    target.rename("new_name")
    codebase.commit()
```

Check first:

```bash
uv run graph-sitter transform ./codemod.py:run /path/to/repo --check
```

Apply only after reviewing the diff:

```bash
uv run graph-sitter transform ./codemod.py:run /path/to/repo --write
```

The transform loader also accepts `Codemod` subclasses or instances with `execute(codebase)`.

## Registered Workspace Codemods

Use the existing `.codegen/codemods` flow when a repo already has registered Graph-sitter functions:

```bash
uv run graph-sitter run LABEL /path/to/repo --check
uv run graph-sitter run LABEL /path/to/repo --write
```

`gs init` and `gs create LABEL` remain available for compatibility.

## Safety Workflow

1. Inspect `git status --short` before editing.
2. Run the codemod with `--check` and inspect the diff.
3. Use `--write` only when the diff matches intent.
4. Run focused tests, type checks, or linters for touched files.
5. Inspect `git diff` after the write.

For strict Rust compact mutation proofs, use `codebase.commit(sync_graph=False)` when the test needs to prove the Python graph stayed unmaterialized. For ordinary user codemods, default `codebase.commit()` is fine unless the repo already uses a stricter pattern.
