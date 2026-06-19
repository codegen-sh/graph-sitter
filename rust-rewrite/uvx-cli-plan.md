# `uvx graph-sitter` CLI And Distribution Plan

## Scope

Own the package entry points and user-facing CLI path for:

- parsing/indexing a local codebase
- running local transformations
- exposing the Rust compact backend through distributed wheels when it is available

This plan does not change docs/site content.

## Current State

- The package distribution name is already `graph-sitter`.
- The current branch exposes both the historical `gs` console script and the canonical `graph-sitter` script:

  ```toml
  [project.scripts]
  gs = "graph_sitter.cli.cli:main"
  graph-sitter = "graph_sitter.cli.cli:main"
  ```

- `uv run gs --help` and `uv run graph-sitter --help` work.
- `graph-sitter parse [PATH] --backend python --format json` works without `.codegen` initialization and emits stable summary JSON.
- `graph-sitter run LABEL PATH --arguments '{"key":"value"}' --backend python` resolves decorated functions under the target repo's `.codegen/codemods`, validates typed Pydantic arguments, and runs without an active `gs init` session.
- `graph_sitter.cli.cli:main` is the public CLI. `graph_sitter.gscli` appears to be an internal generation CLI and should not be used for the `uvx graph-sitter` surface.
- The current `run` path executes decorated functions found under `.codegen/codemods`:
  - `gs init` creates/persists a session for a git repo.
  - `gs create <name>` scaffolds a `@graph_sitter.function("<name>")` function.
  - `gs run <label>` resolves the function by label, parses the repo, runs the function, and applies changes to the local filesystem.
- `src/graph_sitter/cli/commands/run/run_local.py` already has a reusable `parse_codebase(repo_path, subdirectories=None, language=None)` helper.
- `src/codemods/codemod.py` defines a minimal `Codemod` class with an `execute` callback, and integration tests instantiate `Codemod.execute(codebase)`, but the public CLI does not expose this class-based codemod path.
- The Rust rewrite currently has a separate PyO3 module named `graph_sitter_py`. Local source installs do not currently make `import graph_sitter_py` work unless the extension has been built and manually placed on `PYTHONPATH`.

## Proposed Command Surface

Keep `gs` as a backwards-compatible alias. Add `graph-sitter` as the canonical script that `uvx graph-sitter ...` invokes.

### Parse And Inspect

```bash
uvx graph-sitter parse [PATH]
uvx graph-sitter parse [PATH] --backend python|rust|auto
uvx graph-sitter parse [PATH] --language auto|python|typescript
uvx graph-sitter parse [PATH] --subdir src --subdir packages/app
uvx graph-sitter parse [PATH] --format summary|json
uvx graph-sitter parse [PATH] --output graph-sitter-index.json
```

Behavior:

- `PATH` defaults to the current directory.
- The command does not require `.codegen` initialization.
- Default output is a compact human summary: backend, language, files, symbols, imports, exports, references, dependencies, parse errors, wall time.
- `--format json` returns stable JSON suitable for CI and agents.
- `--backend rust` should fail clearly when the Rust extension is unavailable unless `--fallback python` is supplied.
- `--backend auto` can try Rust for supported Python/TypeScript repos and fall back to Python with a JSON field explaining the selected backend.

### Transform Existing Workspace Codemods

```bash
uvx graph-sitter run LABEL [PATH]
uvx graph-sitter run LABEL [PATH] --backend python|rust|auto
uvx graph-sitter run LABEL [PATH] --arguments '{"key":"value"}'
uvx graph-sitter run LABEL [PATH] --diff-preview 200
uvx graph-sitter run LABEL [PATH] --check
uvx graph-sitter run LABEL [PATH] --write
```

Behavior:

- `LABEL` resolves decorated functions under `.codegen/codemods`, matching current `gs run`.
- `PATH` is accepted directly instead of relying only on the globally active session. This is important for repeatable `uvx` and CI usage.
- `--check` should parse and execute in a transaction, print or emit the diff, and exit non-zero if changes would be produced.
- `--write` should apply changes to the filesystem. Current `gs run` writes by default, so the migration should preserve `gs run` behavior while making `graph-sitter run` explicit or at least warning before first write.
- `--arguments` validates JSON when a schema exists and passes typed Pydantic argument models into decorated functions.

### Transform By Import Path

```bash
uvx graph-sitter transform MODULE:OBJECT [PATH]
uvx graph-sitter transform ./codemod.py:run [PATH]
uvx graph-sitter transform ./codemod.py:MyCodemod [PATH] --backend rust --write
```

Behavior:

- `MODULE:OBJECT` allows ad hoc transformations without `gs init` or `.codegen/codemods`.
- If `OBJECT` is a function, call it as `object(codebase)` or `object(codebase, arguments)` when typed arguments are configured.
- If `OBJECT` is a `Codemod` subclass or instance, call `execute(codebase)`.
- This should be implemented after `parse` and `run` because import-path execution needs more validation and clearer sandbox expectations.

### Compatibility Commands

Keep the existing commands reachable through both `gs` and `graph-sitter` unless there is a strong reason to hide one:

```bash
uvx graph-sitter init
uvx graph-sitter create LABEL
uvx graph-sitter list
uvx graph-sitter notebook
```

Rename user-facing text from "codegen function" to "Graph-sitter codemod/function" as a follow-up, but do not block the entry-point alias on copy changes.

## Package Entry-Point Changes

Implemented metadata change:

```toml
[project.scripts]
gs = "graph_sitter.cli.cli:main"
graph-sitter = "graph_sitter.cli.cli:main"
```

Recommended adjacent cleanup:

- Change `@click.version_option(prog_name="codegen", ...)` in `src/graph_sitter/cli/cli.py` to use `graph-sitter` or omit `prog_name` so Click reports the invoked executable name.
- Keep `gs` for backwards compatibility for at least one release after `graph-sitter` is published.
- Do not expose `graph_sitter.gscli.cli:main` as a public script unless it is renamed and documented as an internal developer command.

## Rust Extension Distribution Path

`uvx graph-sitter --backend rust` needs the Rust extension in the installed environment. Today that is not true for a source install unless the developer runs the Rust build and injects the extension directory manually.

Current packaging audit:

- `pyproject.toml` uses `hatchling.build` and does not currently configure `maturin`, `setuptools-rust`, or a custom Rust build hook.
- Existing Hatch wheel hooks cover Cython and package initialization, not the PyO3 crate.
- The PyO3 crate currently builds a top-level `graph_sitter_py` module, and `src/graph_sitter/codebase/rust_backend.py` imports that module directly.
- `rust-rewrite/tools/check_extension_build.sh` proves the extension can compile and import when manually copied onto `PYTHONPATH`, but it does not prove that a built wheel contains the extension.
- Release CI builds wheels through cibuildwheel, but it does not yet install the produced wheel and run `uvx --from dist/<wheel>.whl graph-sitter ...`.

Required packaging decision:

1. Choose a wheel build path for the PyO3 extension:
   - preferred: Hatch-compatible custom build hook that invokes Cargo/PyO3 and includes the built extension in the wheel
   - alternative: switch extension build to `maturin` and integrate with existing Hatch/Cython build requirements
2. Decide the import namespace:
   - short term: continue importing `graph_sitter_py`
   - long term: publish as `graph_sitter._rust` to keep the public namespace cohesive
3. Ensure source distributions include `Cargo.toml`, `Cargo.lock` if locked builds are required, `crates/**`, and tree-sitter grammar dependencies.
4. Keep Rust optional at import time. `graph-sitter parse --backend python` and default library imports must work without the extension.
5. Add wheel smoke tests that install the built artifact into a clean environment and run:

   ```bash
   uvx --from dist/<wheel>.whl graph-sitter --help
   uvx --from dist/<wheel>.whl graph-sitter parse <tiny-python-repo> --backend python --format json
   uvx --from dist/<wheel>.whl graph-sitter parse <tiny-python-repo> --backend rust --format json
   ```

## Implementation Plan

1. [x] Add the `graph-sitter` console script alias and a metadata test proving both `gs` and `graph-sitter` point to `graph_sitter.cli.cli:main`.
2. [x] Add a `parse` command with no `.codegen` or active-session requirement.
3. [ ] Thread `--subdir` through parse construction:
   - `CodebaseConfig(graph_backend=...)`
   - `ProjectConfig.from_path(...)` or equivalent repo/operator construction
4. [x] Add machine-readable JSON output from existing Python properties and Rust compact summary properties.
5. [x] Add an explicit `PATH` argument to `run` while preserving current active-session behavior as fallback.
6. [x] Fix `--arguments` propagation into decorated functions before advertising it as supported.
7. [ ] Add `--check` and `--write` modes for transformations. Preserve `gs run` compatibility separately if needed. Notes: this needs a real no-write sandbox because existing codemods can call `codebase.commit()` internally.
8. Add import-path `transform MODULE:OBJECT` after the command and safety model are tested.
9. Integrate the Rust extension into wheel builds so `--backend rust` works after `uvx` install.

## Test Strategy

Fast tests:

- `uv run python -m py_compile src/graph_sitter/cli/cli.py` and any new command files.
- Metadata unit test:
  - assert `gs` and `graph-sitter` both resolve to `graph_sitter.cli.cli:main` in `pyproject.toml`.
- Click runner tests for:
  - `graph-sitter parse <tmp-git-repo> --backend python --format json` (`tests/unit/cli/commands/parse/test_parse.py`)
  - `graph-sitter parse <tmp-git-repo> --language typescript --backend python --format json`
  - missing Rust extension with `--backend rust` returns a clear error or, when the extension is built locally, returns Rust JSON counts
  - `--backend auto` falls back predictably when Rust is unavailable
- Tiny repo fixtures:
  - Python repo with one class, one function, one import
  - TypeScript repo with one function, one import, one export

Transformation tests:

- Initialize a temp git repo, create a `.codegen/codemods/<label>/<label>.py` decorated function, run `graph-sitter run <label> <repo> --arguments ...`, and assert modified file bytes (`tests/unit/cli/commands/run/test_run.py`).
- Initialize a temp git repo, create a `.codegen/codemods/<label>/<label>.py` decorated function, run `graph-sitter run <label> <repo> --check`, and assert the diff without writing once no-write execution exists.
- Run the same codemod with `--write` and assert modified file bytes.
- Add a codemod with typed arguments and assert `--arguments` reaches the function.
- Add an import-path function and a `Codemod.execute` class fixture once `transform MODULE:OBJECT` exists.

Distribution tests:

- Build a wheel and install it in a clean uv environment.
- Run `uvx --from dist/<wheel>.whl graph-sitter --help`.
- Run parse smoke tests against the installed wheel.
- Run `rust-rewrite/tools/check_extension_build.sh` until wheel packaging owns an equivalent check.
- Add a CI lane that exercises Python 3.12 and 3.13 on Linux/macOS because `requires-python` is currently `>=3.12, <3.14`.

Regression gates:

- Existing focused CLI tests still pass.
- Existing Rust rewrite fast lane still passes when CLI parse uses the Rust compact backend.
- No docs/site files are required for the first entry-point change.

## Blockers And Risks

- `graph-sitter` is now declared as a console script, but it is not available to users until the package is released or installed from this branch.
- The Rust extension is not currently bundled into the Python wheel/source install path, so `--backend rust` cannot be promised to `uvx` users yet.
- `run LABEL PATH` works for local decorated functions, but daemon mode still requires an initialized active session.
- Current local `run` applies changes to the filesystem. A distributed transformation CLI should have explicit `--check` and `--write` modes before being promoted as the primary UX.
- Class-based `Codemod.execute(codebase)` entry points are tested internally but not exposed by the public CLI.
- User-facing CLI copy still says "codegen" in several places. This is not a packaging blocker, but it will make the `graph-sitter` UX feel inconsistent.
- Python version support is narrow (`>=3.12, <3.14`), so `uvx` examples should specify a compatible Python when needed, for example `uvx --python 3.13 graph-sitter ...`.
