# `uvx graph-sitter` Command Roadmap

## Scope

This track owns the public one-shot command experience for parsing repositories
and running transformations through `uvx graph-sitter ...`.

It is intentionally separate from the active wheel-build work. The integrator
currently owns `src/gsbuild/**`, `hatch.toml`, `uv.lock`,
`.github/workflows/rust-rewrite-extension.yml`, and focused wheel smoke tests.
This roadmap names the contract those changes need to satisfy without editing
those files.

## Audit Summary

Current package metadata declares both scripts:

```toml
[project.scripts]
gs = "graph_sitter.cli.cli:main"
graph-sitter = "graph_sitter.cli.cli:main"
```

`graph_sitter.cli.cli:main` is the public CLI. `graph_sitter.gscli` should stay
out of the `uvx graph-sitter` contract unless it is renamed and documented
separately.

Implemented local command surfaces:

- `graph-sitter parse [PATH]` parses a local repo without `.codegen` initialization.
- `graph-sitter run LABEL [PATH]` runs registered `.codegen/codemods` functions and keeps the historical active-session fallback.
- `graph-sitter transform MODULE:OBJECT [PATH] --check|--write` runs ad hoc import-path transforms without `.codegen` registration.

Observed help output confirms these shared options:

- `--backend python|rust|auto`
- `--fallback python|error`
- `--language auto|python|typescript`

Existing focused tests cover:

- console-script metadata for `gs` and `graph-sitter`
- Python and TypeScript `parse --backend python --format json`
- clean missing-extension behavior for `parse --backend rust --fallback error`
- `run LABEL PATH` with typed arguments and codemod file mutation
- `run LABEL PATH --check` sandbox behavior
- import-path `transform` function and `Codemod` subclass mutation
- import-path `transform --check` sandbox behavior
- transform safety errors for missing mode and conflicting `--check --write`

Important gap: these tests prove local package behavior. They do not yet prove
published/wheel-installed `uvx graph-sitter ...` behavior, nor Rust-backend
transform parity.

## Final Command Contract

### Entry Point

Canonical command:

```bash
uvx graph-sitter ...
```

Compatibility alias:

```bash
uvx --from graph-sitter gs ...
```

The package should continue exposing `gs` as a console script for existing
users, but new docs and examples should use `graph-sitter`.

### Parse

Primary form:

```bash
uvx graph-sitter parse [PATH]
```

Supported modes:

```bash
uvx graph-sitter parse [PATH] --language auto|python|typescript
uvx graph-sitter parse [PATH] --backend python|rust|auto
uvx graph-sitter parse [PATH] --fallback error|python
uvx graph-sitter parse [PATH] --format summary|json
```

Planned parse extensions:

```bash
uvx graph-sitter parse [PATH] --subdir src --subdir packages/app
uvx graph-sitter parse [PATH] --output graph-sitter-index.json
uvx graph-sitter parse [PATH] --format jsonl
```

Contract:

- `PATH` defaults to the current directory.
- The command must not require `gs init`, `.codegen`, a daemon, or an active session.
- `--format summary` is human-readable and may change copy.
- `--format json` is machine-readable and should remain stable within a major version.
- JSON output must include at least `path`, `backend_requested`, `backend`, `language`, `elapsed_seconds`, `files`, `symbols`, `classes`, `functions`, `global_variables`, `imports`, `exports`, `references`, `external_references`, `dependencies`, `subclass_edges`, `files_with_errors`, and `rust_backend_error`.
- `--backend python` always uses the Python object graph.
- `--backend rust --fallback error` must either use the Rust backend or exit non-zero with a clear error.
- `--backend rust --fallback python` may fall back to Python and must report the reason in `rust_backend_error`.
- `--backend auto` may choose Rust for supported repositories and fall back to Python for unsupported cases; JSON output must disclose the actual `backend`.
- Current branch default is `--backend python`. Final default should become `--backend auto` only after published-wheel smoke tests, large-repo gates, and P0 parity gates are green.

### Registered Codemods

Primary form:

```bash
uvx graph-sitter run LABEL [PATH]
```

Supported modes:

```bash
uvx graph-sitter run LABEL [PATH] --arguments '{"key":"value"}'
uvx graph-sitter run LABEL [PATH] --diff-preview 200
uvx graph-sitter run LABEL [PATH] --backend python|rust|auto
uvx graph-sitter run LABEL [PATH] --fallback python|error
uvx graph-sitter run LABEL [PATH] --language auto|python|typescript
uvx graph-sitter run LABEL [PATH] --check
uvx graph-sitter run LABEL [PATH] --write
```

Contract:

- `LABEL` resolves decorated functions under `.codegen/codemods`.
- `PATH` enables repeatable uvx/CI usage without an active `gs init` session.
- Omitting `PATH` may keep the historical active-session behavior.
- `--arguments` accepts a JSON object and validates typed Pydantic argument models when present.
- `--check` runs against a temporary copied repository, prints the produced diff, leaves the target unchanged, and exits non-zero when changes would be produced.
- `--write` applies changes to the target repo.
- For compatibility, current `run` may still write by default. New docs should show explicit `--check` or `--write`.
- `--daemon` is compatibility-only and should not be part of the core `uvx` story because it requires initialized session state.

### Import-Path Transforms

Primary form:

```bash
uvx graph-sitter transform MODULE:OBJECT [PATH] --check
uvx graph-sitter transform MODULE:OBJECT [PATH] --write
```

Examples:

```bash
uvx graph-sitter transform ./codemod.py:run ./repo --check
uvx graph-sitter transform ./codemod.py:RenameFunction ./repo --write --arguments '{"new_name":"renamed"}'
uvx graph-sitter transform transforms.rename:run ./repo --backend rust --fallback error --check
```

Contract:

- `MODULE` may be an importable module or a Python file path.
- `OBJECT` may be a function, a `codemods.codemod.Codemod` subclass/instance, or an object exposing callable `execute`.
- Callable targets receive `codebase` and optionally `arguments`.
- `--check` and `--write` are mutually exclusive.
- One of `--check` or `--write` is required.
- `--check` must never mutate the target repo, including when a codemod calls `codebase.commit()`.
- `--write` may mutate the target repo and should print a clear success or no-op message.

### Backend And Fallback Semantics

Backend selection is shared by `parse`, `run`, and `transform`.

| Request | Rust unavailable | Unsupported Rust API during transform |
| --- | --- | --- |
| `--backend python` | Not relevant | Not relevant |
| `--backend rust --fallback error` | Exit non-zero | Exit non-zero |
| `--backend rust --fallback python` | Fall back to Python | Fall back to Python graph if possible |
| `--backend auto --fallback python` | Fall back to Python | Fall back to Python graph if possible |

The CLI should prefer explicit failure in examples that are meant to prove Rust behavior:

```bash
uvx graph-sitter parse ./repo --backend rust --fallback error --format json
```

The CLI should prefer resilient behavior in user-facing docs before Rust parity is complete:

```bash
uvx graph-sitter parse ./repo --backend auto --fallback python --format summary
```

### Distribution Contract

A released package is ready for the public `uvx graph-sitter` story only when
these smoke tests pass from an artifact, not just a checkout:

```bash
uvx --from dist/graph_sitter-*.whl graph-sitter --help
uvx --from dist/graph_sitter-*.whl graph-sitter parse ./tiny-python --backend python --format json
uvx --from dist/graph_sitter-*.whl graph-sitter parse ./tiny-python --backend rust --fallback error --format json
uvx --from dist/graph_sitter-*.whl graph-sitter transform ./rename.py:run ./tiny-python --check
uvx --from dist/graph_sitter-*.whl graph-sitter transform ./rename.py:run ./tiny-python --write
```

Release docs should include a compatible Python selector while package support remains `>=3.12,<3.14`:

```bash
uvx --python 3.13 graph-sitter parse ./repo --format summary
```

## Multi-Agent Checklist

### Contract And Docs

- [ ] Reconcile this roadmap with `rust-rewrite/uvx-cli-plan.md` after the integrator lands active wheel-packaging edits. owner: CLI/distribution agent.
- [ ] Update skill docs to use explicit `--check` or `--write` in every transform example. owner: skill/docs agent.
- [ ] Update public setup docs with `uvx --python 3.13 graph-sitter parse ...` once a release artifact exists. owner: docs/site agent.
- [ ] Replace remaining user-facing "codegen function" copy in `graph-sitter run --help` with Graph-sitter/codemod wording. owner: CLI UX agent.

### Parse Implementation

- [ ] Add repeatable `--subdir` support to `graph-sitter parse`. owner: CLI implementation agent.
- [ ] Add `--output` for JSON output files once the JSON schema is stable. owner: CLI implementation agent.
- [ ] Decide whether `jsonl` belongs in v1 or should wait for a richer graph export command. owner: CLI/distribution agent.
- [ ] Version the parse JSON schema or document its stability policy. owner: CLI/contracts agent.
- [ ] Add `--backend auto` unit coverage for unavailable Rust fallback and selected-backend disclosure. owner: test agent.

### Transform Implementation

- [x] Add uvx-level import-path transform smokes from a built wheel for both `--check` and `--write`. owner: codex. Result: `check_wheel_rust_backend.sh` runs a file-based transform from the built wheel in strict Rust mode, proves `--check` reports a diff without mutating the target repo, then proves `--write` mutates the target repo.
- [ ] Add Rust-backend transform tests that either pass fully or fail/fallback according to `--fallback`. owner: parity/test agent.
- [ ] Add a no-op transform test for `--check` returning exit zero and "No changes would be produced". owner: CLI test agent.
- [ ] Decide whether `run` should eventually require explicit `--check` or `--write` in a major release. owner: CLI/contracts agent.

### Packaging And Release

- [x] Prove built wheels include `codemods` and `graph_sitter_py` in clean uv environments. owner: codex. Result: `check_wheel_rust_backend.sh` asserts both wheel contents and imports the CLI from a clean `uvx --from dist/<wheel>.whl` environment.
- [x] Add Linux and macOS wheel uvx smokes for Python 3.12 and 3.13. owner: codex. Result: `.github/workflows/rust-rewrite-extension.yml` runs `check_wheel_rust_backend.sh` across the supported Python/OS matrix.
- [x] Add artifact-level smoke for `--backend rust --fallback error` before advertising Rust-backed uvx parse. owner: codex. Result: branch-built wheel CI runs strict Rust parse and strict Rust transform smokes from the installed artifact.
- [ ] Add release checklist entry requiring `uvx graph-sitter --help`, parse, and transform against the uploaded artifact. owner: release agent.
- [ ] Decide long-term Rust extension import namespace: keep top-level `graph_sitter_py` or move to `graph_sitter._rust`. owner: packaging/API agent.

### Correctness And Benchmarks

- [ ] Add pinned large Python repo `uvx parse --backend rust --fallback error` benchmark from a wheel artifact. owner: benchmark agent.
- [ ] Add pinned large TypeScript repo `uvx parse --backend rust --fallback error` benchmark from a wheel artifact. owner: benchmark agent.
- [ ] Add pinned codemod fixtures that assert file diffs, not just graph counts. owner: codemod parity agent.
- [ ] Compare Rust and Python backend transform diffs for the same pinned codemods. owner: codemod parity agent.

## Blockers

- Public `uvx graph-sitter` availability still requires a released package or explicit `uvx --from` source/artifact usage.
- Rust-backed uvx parsing depends on bundled/importable PyO3 wheels; checkout-local extension builds are not enough for public docs.
- Rust-backed transformations are only ready when the transform APIs used by codemods either work through Rust handles or fall back according to `--fallback`.
- Defaulting to `--backend auto` should wait until P0 parity, artifact smoke tests, and large-repo gates prove the Rust backend is the safer default for supported languages.
