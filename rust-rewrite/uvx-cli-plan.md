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
- `uvx --from <local checkout> graph-sitter --help` resolves to the packaged console script once the checkout is installable in uv's temporary environment.
- Local `uvx --from <checkout> graph-sitter parse <repo> --backend python --format json` now works on Python 3.12 and 3.13 after constraining parser/runtime dependencies to the lock-compatible ranges.
- `uvx --from dist/<wheel>.whl graph-sitter ...` is now the release-wheel smoke path: the Hatch custom wheel hook builds and bundles `graph_sitter_py`, and `rust-rewrite/tools/check_wheel_rust_backend.sh` proves the installed wheel can run `--help`, parse through both Python and strict Rust backends, and run import-path transforms in strict Rust `--check` and `--write` modes.
- `graph-sitter parse [PATH] --backend python --format json` works without `.codegen` initialization and emits stable summary JSON.
- `graph-sitter run LABEL PATH --arguments '{"key":"value"}' --backend python` resolves decorated functions under the target repo's `.codegen/codemods`, validates typed Pydantic arguments, and runs without an active `gs init` session.
- `graph-sitter run LABEL PATH --check` runs in a temporary copied-repo sandbox, reports the semantic diff, and leaves the target repo unchanged.
- `graph-sitter transform MODULE:OBJECT PATH --check|--write` loads ad hoc file or module transforms, supports plain functions plus `Codemod.execute` classes/instances, requires explicit `--check` or `--write`, and uses the same backend/language/check/write path as `run`.
- The Hatch wheel package list now includes both `src/graph_sitter` and `src/codemods` so `codemods.codemod.Codemod` is importable in clean `uvx` environments.
- `graph_sitter.cli.cli:main` is the public CLI. `graph_sitter.gscli` appears to be an internal generation CLI and should not be used for the `uvx graph-sitter` surface.
- The current `run` path executes decorated functions found under `.codegen/codemods`:
  - `gs init` creates/persists a session for a git repo.
  - `gs create <name>` scaffolds a `@graph_sitter.function("<name>")` function.
  - `gs run <label>` resolves the function by label, parses the repo, runs the function, and applies changes to the local filesystem.
- `src/graph_sitter/cli/commands/run/run_local.py` already has a reusable `parse_codebase(repo_path, subdirectories=None, language=None)` helper.
- `src/codemods/codemod.py` defines a minimal `Codemod` class with an `execute` callback, and the public `graph-sitter transform MODULE:OBJECT` path now supports `Codemod` subclasses and instances.
- The Rust rewrite currently has a separate PyO3 module named `graph_sitter_py`. Built wheels now include that top-level module; source/editable development can still use the manual extension build helpers when bypassing wheel builds.

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
- `--check` runs the codemod in a temporary copied repository, prints the produced diff, leaves the target repository untouched, and exits non-zero if changes would be produced.
- `--write` applies changes to the filesystem. Current `gs run` writes by default, so the migration preserves default write behavior while making explicit write intent available.
- `--arguments` validates JSON when a schema exists and passes typed Pydantic argument models into decorated functions.

### Transform By Import Path

```bash
uvx graph-sitter transform MODULE:OBJECT [PATH] --check
uvx graph-sitter transform MODULE:OBJECT [PATH] --write
uvx graph-sitter transform ./codemod.py:run [PATH] --check
uvx graph-sitter transform ./codemod.py:MyCodemod [PATH] --backend rust --write
```

Behavior:

- `MODULE:OBJECT` allows ad hoc transformations without `gs init` or `.codegen/codemods`.
- If `OBJECT` is a function, call it as `object(codebase)` or `object(codebase, arguments)` when typed arguments are configured.
- If `OBJECT` is a `Codemod` subclass or instance, call `execute(codebase)`.
- `--check` runs the transform in a temporary copied repository, prints the produced diff, leaves the target repository untouched, and exits non-zero if changes would be produced.
- `--write` applies changes to the filesystem. Unlike the backwards-compatible `run` command, `transform` requires an explicit mode because it is a new import-path surface.
- This now shares the same target-repo parser, typed `--arguments`, and temporary copied-repo `--check` sandbox as `run`.

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

Implemented adjacent cleanup:

- `@click.version_option(...)` in `src/graph_sitter/cli/cli.py` now uses `prog_name="graph-sitter"` instead of the historical `codegen` name.
- `hatch.toml` packages `src/codemods` alongside `src/graph_sitter`; without this, `uvx --from <checkout> graph-sitter --help` fails while importing the `transform` command.
- `pyproject.toml` constrains `tree-sitter`, tree-sitter grammar packages, and `mini-racer` to the versions/ranges exercised by the lockfile so clean `uvx --from` installs do not pick incompatible parser or JavaScript-runtime wheels.
- Keep `gs` for backwards compatibility for at least one release after `graph-sitter` is published.
- Do not expose `graph_sitter.gscli.cli:main` as a public script unless it is renamed and documented as an internal developer command.

## Rust Extension Distribution Path

`uvx graph-sitter --backend rust` needs the Rust extension in the installed environment. The rust-rewrite branch now builds the PyO3 extension during wheel construction and force-includes it as the top-level `graph_sitter_py` module.

Current packaging audit:

- `pyproject.toml` uses `hatchling.build`; the selected path is the existing Hatch custom hook rather than `maturin` or `setuptools-rust`.
- Existing Hatch wheel hooks cover Cython, package initialization, and now the PyO3 crate.
- The PyO3 crate currently builds a top-level `graph_sitter_py` module, and `src/graph_sitter/codebase/rust_backend.py` imports that module directly.
- `rust-rewrite/tools/check_extension_build.sh` proves the extension can compile and import when manually copied onto `PYTHONPATH`, but it does not prove that a built wheel contains the extension.
- `rust-rewrite/tools/check_wheel_rust_backend.sh` builds a wheel, asserts it contains `graph_sitter_py` and `codemods`, installs it through `uvx --from dist/<wheel>.whl`, parses tiny Python and TypeScript repos with strict Rust, validates Python parsing, and runs a strict Rust import-path transform with both `--check` and `--write`.
- `.github/workflows/rust-rewrite-extension.yml` runs the wheel smoke on Linux and macOS for Python 3.12 and 3.13.

Required packaging decision:

1. Chosen wheel build path for the PyO3 extension: Hatch-compatible custom build hook that invokes Cargo/PyO3 and includes the built extension in the wheel.
2. Decide the import namespace:
   - short term: continue importing `graph_sitter_py`
   - long term: publish as `graph_sitter._rust` to keep the public namespace cohesive
3. Ensure source distributions include `Cargo.toml`, `Cargo.lock` if locked builds are required, `crates/**`, and tree-sitter grammar dependencies.
4. Keep Rust optional at import time. `graph-sitter parse --backend python` and default library imports must work without the extension.
5. Wheel smoke tests install the built artifact into a clean environment and run:

   ```bash
   uvx --from dist/<wheel>.whl graph-sitter --help
   uvx --from dist/<wheel>.whl graph-sitter parse <tiny-python-repo> --backend python --format json
   uvx --from dist/<wheel>.whl graph-sitter parse <tiny-python-repo> --backend rust --format json
   uvx --from dist/<wheel>.whl graph-sitter parse <tiny-typescript-repo> --language typescript --backend rust --fallback error --format json
   uvx --from dist/<wheel>.whl graph-sitter transform <transform.py>:rename <tiny-python-repo> --backend rust --fallback error --check
   uvx --from dist/<wheel>.whl graph-sitter transform <transform.py>:rename <tiny-python-repo> --backend rust --fallback error --write
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
7. [x] Add `--check` and `--write` modes for transformations. Preserve `gs run` compatibility separately if needed. Result: `--check` uses a temporary copied-repo sandbox so codemods that call `codebase.commit()` internally cannot touch the target repo; `--write` is explicit while default write behavior remains for compatibility.
8. [x] Add import-path `transform MODULE:OBJECT` after the command and safety model are tested. Result: file/module import paths can run plain functions, `Codemod` subclasses, and `Codemod` instances with `--check`, `--write`, backend/language flags, and typed arguments.
9. [x] Enforce explicit import-path transform mode. Result: `graph-sitter transform MODULE:OBJECT PATH` now fails until the user chooses `--check` or `--write`.
10. [x] Make the Python-backend `uvx --from <checkout>` path executable. Result: include `codemods` in the wheel package list and constrain clean-install dependency resolution for tree-sitter and `mini-racer`.
11. [x] Integrate the Rust extension into wheel builds so `--backend rust` works after `uvx` install. Result: `src/gsbuild/build.py` builds `graph-sitter-py` through Cargo, force-includes `graph_sitter_py{EXT_SUFFIX}` into wheels, marks wheels platform-specific, and `check_wheel_rust_backend.sh` proves `uvx --from dist/<wheel>.whl graph-sitter parse --backend rust --fallback error`.
12. [x] Add artifact-level transform smokes from a built wheel. Result: `check_wheel_rust_backend.sh` now also proves `graph-sitter --help`, Python parse, strict Rust import-path `transform --check` without target mutation, and strict Rust import-path `transform --write` with target mutation from the built wheel.
13. [x] Add artifact-level TypeScript strict Rust parse smoke from a built wheel. Result: `check_wheel_rust_backend.sh` now also proves `graph-sitter parse <tiny-typescript-repo> --language typescript --backend rust --fallback error --format json` from the built wheel.

## Test Strategy

Fast tests:

- `uv run python -m py_compile src/graph_sitter/cli/cli.py` and any new command files.
- Metadata unit test:
  - assert `gs` and `graph-sitter` both resolve to `graph_sitter.cli.cli:main` in `pyproject.toml`.
  - assert clean-uvx dependency constraints and Hatch package inclusion for `codemods` stay declared.
  - assert the Hatch custom wheel hook builds the Rust extension by default and CI exercises the installed-wheel Rust smoke.
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
- Initialize a temp git repo, create a `.codegen/codemods/<label>/<label>.py` decorated function, run `graph-sitter run <label> <repo> --check`, assert the semantic diff, and assert original file bytes are unchanged.
- Run the same codemod with `--write` and assert modified file bytes.
- Add a codemod with typed arguments and assert `--arguments` reaches the function.
- Add an import-path function and a `Codemod.execute` class fixture (`tests/unit/cli/commands/transform/test_transform.py`).
- Assert import-path `transform` rejects missing mode and rejects `--check --write` together.

Distribution tests:

- Build a wheel and install it in a clean uv environment.
- Run `uvx --from dist/<wheel>.whl graph-sitter --help`.
- Run Python and Rust parse smoke tests against the installed wheel for Python and TypeScript fixtures.
- Run import-path transform `--check` and `--write` smoke tests against the installed wheel.
- Keep `rust-rewrite/tools/check_extension_build.sh` for direct PyO3 diagnostics; use `rust-rewrite/tools/check_wheel_rust_backend.sh` for the distribution proof.
- Add a CI lane that exercises Python 3.12 and 3.13 on Linux/macOS because `requires-python` is currently `>=3.12, <3.14`.

Regression gates:

- Existing focused CLI tests still pass.
- Existing Rust rewrite fast lane still passes when CLI parse uses the Rust compact backend.
- No docs/site files are required for the first entry-point change.

## Blockers And Risks

- `graph-sitter` is now declared as a console script, but it is not available to users until the package is released or installed from this branch. Local proof now passes with `uvx --from <checkout> graph-sitter ...`; release proof uses `uvx --from dist/<wheel>.whl graph-sitter ...`.
- Rust backend support is bundled into wheels built from this branch, and CI validates branch-built wheel parse/transform smokes. Published package validation is still required before public docs should imply availability from PyPI.
- `run LABEL PATH` works for local decorated functions, but daemon mode still requires an initialized active session.
- Current local `run` still applies changes by default for compatibility. The newer import-path `transform` surface requires explicit `--check` or `--write`.
- Import-path `transform` supports class-based `Codemod.execute(codebase)` entry points, but package-discoverable transform registries are not implemented.
- User-facing CLI copy still says "codegen" in several places. This is not a packaging blocker, but it will make the `graph-sitter` UX feel inconsistent.
- Python version support is narrow (`>=3.12, <3.14`), so `uvx` examples should specify a compatible Python when needed, for example `uvx --python 3.13 graph-sitter ...`.
