# CLI Reference

Use this when the user asks for `graph-sitter`, `gs`, `uvx graph-sitter`, `parse`, `run`, or `transform` workflows.

## Current Local Surface

The rust-rewrite branch exposes both console scripts:

```bash
uv run gs --help
uv run graph-sitter --help
```

Use `graph-sitter` for new examples and keep `gs` as the compatibility alias. `graph_sitter.cli.cli:main` is the public CLI entry point; do not use `graph_sitter.gscli` for the `uvx graph-sitter` surface.

## Parse

Local source checkout:

```bash
uv run graph-sitter parse [PATH] --backend python --language auto --format json
```

Installed/distributed package path:

```bash
uvx graph-sitter parse [PATH] --backend python --language auto --format json
```

Supported options in this branch:

- `--backend python|rust|auto`
- `--fallback python|error`
- `--language auto|python|typescript`
- `--format summary|json`

The command does not require `.codegen` initialization. Use `--backend python` for reliable distributed examples until wheels include the Rust extension.

## Transform By Import Path

Run ad hoc functions or `Codemod.execute` classes/instances without `.codegen/codemods` registration:

```bash
uv run graph-sitter transform MODULE:OBJECT [PATH] --check
uv run graph-sitter transform ./codemod.py:run [PATH] --check
uv run graph-sitter transform ./codemod.py:MyCodemod [PATH] --write
```

For installed package flows, replace `uv run` with `uvx graph-sitter`.

Useful options:

- `--check`: run in a temporary copied-repo sandbox, print the diff, leave the target unchanged, and exit non-zero when changes would be produced.
- `--write`: apply changes to the target repo. This remains the default for compatibility, but use it explicitly in instructions.
- `--arguments '{"key":"value"}'`: pass JSON to a transform with an `arguments` parameter; Pydantic models are validated when present.
- `--backend python|rust|auto`, `--fallback python|error`, `--language auto|python|typescript`.

## Registered Codemods

For existing `.codegen/codemods` functions:

```bash
uv run graph-sitter run LABEL [PATH] --check
uv run graph-sitter run LABEL [PATH] --write
```

`gs init`, `gs create`, `gs list`, and `gs notebook` remain compatibility commands.

## Distribution Status

The `uvx graph-sitter ...` command direction is correct for public one-shot usage, and `parse` plus `transform MODULE:OBJECT` are implemented locally. Rust backend support from `uvx` is not ready until built wheels bundle and import the PyO3 extension.
