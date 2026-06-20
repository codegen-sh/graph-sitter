# `uvx graph-sitter` Command Roadmap

## Scope

This track owns the public one-shot command experience for parsing repositories
and running transformations through `uvx graph-sitter ...`.

Product direction:

- Python remains the shell, public API, and codemod authoring language.
- Rust is the scale backend used by the shell when requested or selected.
- The public command should eventually be runnable as `uvx graph-sitter ...`
  without local setup, checkout-specific paths, `gs init`, or a daemon.
- The same command contract must be usable by docs, release gates, CI, and the
  Graph-sitter skill distribution.

This file intentionally stays separate from implementation and wheel-building
work. The integrator currently owns `src/gsbuild/**`, `hatch.toml`, `uv.lock`,
`.github/workflows/rust-rewrite-extension.yml`, and focused wheel smoke tests.

## Command Taxonomy At A Glance

The public `uvx` story should have three user-facing lanes:

| Lane | Command | Requires `.codegen`? | Mutates target? | Primary user |
| --- | --- | --- | --- | --- |
| Inspect | `uvx graph-sitter parse [PATH]` | No | Never | Humans, CI, agents, benchmarks |
| Registered codemod | `uvx graph-sitter run LABEL [PATH] --check|--write` | Yes, for `LABEL` lookup | Only with `--write` or compatibility default | Repos that own codemods |
| One-shot transform | `uvx graph-sitter transform MODULE:OBJECT [PATH] --check|--write` | No | Only with `--write` | Agents, release gates, external codemods |

Supporting lane:

| Lane | Command | Purpose |
| --- | --- | --- |
| Diagnostics | `uvx graph-sitter doctor [--backend rust] [--json]` | Prove package, parser dependency, and optional Rust-backend readiness before parse or transform workflows |

The canonical spelling is `graph-sitter`. The historical `gs` script remains a
compatibility alias, but new docs, skills, benchmark scripts, and release gates
should use `uvx graph-sitter ...`.

Minimum public examples:

```bash
uvx --python 3.13 graph-sitter doctor --json
uvx --python 3.13 graph-sitter parse . --language python --backend auto --fallback python --format json
uvx --python 3.13 graph-sitter run rename-symbol . --arguments '{"new_name":"renamed"}' --check
uvx --python 3.13 graph-sitter transform ./codemods/rename.py:rename . --arguments '{"new_name":"renamed"}' --check
```

Strict Rust and branch-artifact examples:

```bash
uvx --python 3.13 --from dist/<wheel>.whl graph-sitter doctor --backend rust --language python --json
uvx --python 3.13 --from dist/<wheel>.whl graph-sitter parse ./repo --language typescript --backend rust --fallback error --format json
uvx --python 3.13 --from dist/<wheel>.whl graph-sitter transform ./codemods/rename.py:rename ./repo --backend rust --fallback error --check
```

## Packaging Constraints For `uvx`

- The distribution name must remain `graph-sitter`, and the `graph-sitter`
  console script must resolve to `graph_sitter.cli.cli:main`.
- Keep `gs` as a compatibility script, but do not use it as the primary
  published-package or skill-facing command.
- Public examples should pin `--python 3.13` while package metadata remains
  constrained to Python `>=3.12,<3.14`.
- Rust-backed `uvx` requires wheels that include the platform-specific
  `graph_sitter_py` extension. Python-backend imports must remain safe when the
  extension is absent.
- Clean `uvx` environments must include `codemods/codemod.py`, parser runtime
  dependencies, and compatible tree-sitter grammar wheels.
- Branch proof uses `uvx --from dist/<wheel>.whl graph-sitter ...`; release
  proof must use uploaded artifacts with
  `uvx --from graph-sitter==<version> graph-sitter ...`, then the default
  `uvx graph-sitter ...` spelling.
- Do not advertise `--backend rust` from PyPI until uploaded Linux/macOS wheels
  pass parse and transform smokes for Python 3.12 and 3.13.
- If an sdist is published, it must include the Rust crate sources and any
  build inputs needed to compile the PyO3 extension.

## Source Audit

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

- `graph-sitter parse [PATH]` parses a local repo without `.codegen`
  initialization.
- `graph-sitter run LABEL [PATH]` runs registered `.codegen/codemods`
  functions and keeps the historical active-session fallback.
- `graph-sitter transform MODULE:OBJECT [PATH] --check|--write` runs ad hoc
  import-path transforms without `.codegen` registration.
- `graph-sitter doctor [--backend python|rust] [--json]` reports local
  installation, dependency, and optional Rust-backend readiness.

Observed command options from the current Click implementations:

| Command | Required args | Shared options | Mode/output options |
| --- | --- | --- | --- |
| `parse` | optional `PATH` | `--backend python|rust|auto`, `--fallback python|error`, `--language auto|python|typescript` | `--format summary|json` |
| `run` | `LABEL`, optional `PATH` | `--backend python|rust|auto`, `--fallback python|error`, `--language auto|python|typescript` | `--arguments JSON`, `--diff-preview N`, `--check`, `--write`, `--daemon` |
| `transform` | `MODULE:OBJECT`, optional `PATH` | `--backend python|rust|auto`, `--fallback python|error`, `--language auto|python|typescript` | `--arguments JSON`, `--diff-preview N`, `--check`, `--write` |
| `doctor` | none | `--backend python|rust`, `--language python|typescript` | `--json` |

Current defaults:

- `parse --backend python --fallback error --language auto --format summary`
- `run --backend python --fallback python --language auto`
- `transform --backend python --fallback python --language auto`

Current safety semantics:

- `parse` is read-only.
- `run --check` copies the target repo into a temporary sandbox, prints the
  produced diff, leaves the original target unchanged, and exits `1` when
  changes would be produced.
- `run --write` applies changes. For compatibility, `run` still writes by
  default when neither `--check` nor `--write` is supplied.
- `transform` requires exactly one of `--check` or `--write`.
- `transform --check` uses the same copied-repo sandbox as `run --check`.

Focused local tests cover:

- console-script metadata for `gs` and `graph-sitter`
- Python and TypeScript `parse --backend python --format json`
- clean strict Rust failure behavior when the Rust extension is unavailable
- `run LABEL PATH` with typed arguments and codemod file mutation
- `run LABEL PATH --check` sandbox behavior
- import-path `transform` function mutation
- import-path `transform` `Codemod` subclass mutation
- import-path `transform --check` sandbox behavior
- transform safety errors for missing mode and conflicting `--check --write`

## Final User-Facing Command Shape

### Entry Point

Canonical command:

```bash
uvx graph-sitter ...
```

Pinned or artifact-specific command:

```bash
uvx --python 3.13 --from graph-sitter==<version> graph-sitter ...
uvx --python 3.13 --from dist/graph_sitter-<version>-<tags>.whl graph-sitter ...
```

Compatibility alias:

```bash
uvx --from graph-sitter gs ...
```

The package should continue exposing `gs` as a console script for existing
users, but new docs, release gates, and skills should use `graph-sitter`.

### Parse

Primary form:

```bash
uvx graph-sitter parse [PATH]
```

Supported current modes:

```bash
uvx graph-sitter parse [PATH] --language auto|python|typescript
uvx graph-sitter parse [PATH] --backend python|rust|auto
uvx graph-sitter parse [PATH] --fallback error|python
uvx graph-sitter parse [PATH] --format summary|json
uvx graph-sitter parse [PATH] --subdir src --subdir packages/app
```

Python repo examples:

```bash
uvx --python 3.13 graph-sitter parse ./airflow --language python --backend auto --fallback python --format summary
uvx --python 3.13 graph-sitter parse ./airflow --language python --backend rust --fallback error --format json
```

TypeScript repo examples:

```bash
uvx --python 3.13 graph-sitter parse ./next.js --language typescript --backend auto --fallback python --format summary
uvx --python 3.13 graph-sitter parse ./next.js --language typescript --backend rust --fallback error --format json
```

Planned parse extensions:

```bash
uvx graph-sitter parse [PATH] --output graph-sitter-index.json
uvx graph-sitter parse [PATH] --format jsonl
```

Contract:

- `PATH` defaults to the current directory.
- The command must not require `gs init`, `.codegen`, a daemon, or an active
  session.
- `--format summary` is human-readable and may change copy.
- `--format json` is machine-readable and should remain stable within a major
  version.
- JSON output must include at least `path`, `backend_requested`, `backend`,
  `language`, `elapsed_seconds`, `subdirectories`, `files`, `symbols`,
  `classes`, `functions`, `global_variables`, `imports`, `exports`, `references`,
  `external_references`, `dependencies`, `subclass_edges`, `files_with_errors`,
  and `rust_backend_error`.
- `--subdir` may be passed more than once. Paths are resolved relative to
  `PATH`; absolute paths are accepted only when they are inside the repository.
  Directory filters feed the same file-discovery path used by both Python and
  Rust backends.
- `--backend python` always uses the Python object graph.
- `--backend rust --fallback error` must either use the Rust backend or exit
  non-zero with a clear error.
- `--backend rust --fallback python` may fall back to Python and must report
  the reason in `rust_backend_error`.
- `--backend auto` may choose Rust for supported repositories and fall back to
  Python for unsupported cases; JSON output must disclose the actual `backend`.
- Current branch default is `--backend python`. Final default should become
  `--backend auto` only after published-package smokes, large-repo gates, and
  P0 parity gates are green.

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

Python registered-codemod examples:

```bash
uvx --python 3.13 graph-sitter run rename-target ./service --language python --backend auto --fallback python --arguments '{"new_name":"renamed"}' --check
uvx --python 3.13 graph-sitter run rename-target ./service --language python --backend auto --fallback python --arguments '{"new_name":"renamed"}' --write
```

TypeScript registered-codemod examples:

```bash
uvx --python 3.13 graph-sitter run rename-component ./next.js --language typescript --backend auto --fallback python --arguments '{"new_name":"RenamedCard"}' --check
uvx --python 3.13 graph-sitter run rename-component ./next.js --language typescript --backend auto --fallback python --arguments '{"new_name":"RenamedCard"}' --write
```

Contract:

- `LABEL` resolves decorated functions under `.codegen/codemods`.
- `PATH` enables repeatable uvx/CI usage without an active `gs init` session.
- Omitting `PATH` may keep the historical active-session behavior.
- `--arguments` accepts a JSON object and validates typed Pydantic argument
  models when present.
- `--check` runs against a temporary copied repository, prints the produced
  diff, leaves the target unchanged, and exits non-zero when changes would be
  produced.
- `--write` applies changes to the target repo.
- For compatibility, current `run` may still write by default. New docs and
  skills should always show explicit `--check` or `--write`.
- `--daemon` is compatibility-only and should not be part of the core `uvx`
  story because it requires initialized session state.

### Import-Path Transforms

Primary form:

```bash
uvx graph-sitter transform MODULE:OBJECT [PATH] --check
uvx graph-sitter transform MODULE:OBJECT [PATH] --write
```

Python transform examples:

```bash
uvx --python 3.13 graph-sitter transform ./codemods/rename.py:rename ./service --language python --backend auto --fallback python --arguments '{"new_name":"renamed"}' --check
uvx --python 3.13 graph-sitter transform ./codemods/rename.py:rename ./service --language python --backend auto --fallback python --arguments '{"new_name":"renamed"}' --write
```

TypeScript transform examples:

```bash
uvx --python 3.13 graph-sitter transform ./codemods/rename_component.py:rename ./next.js --language typescript --backend auto --fallback python --arguments '{"new_name":"RenamedCard"}' --check
uvx --python 3.13 graph-sitter transform ./codemods/rename_component.py:rename ./next.js --language typescript --backend rust --fallback error --arguments '{"new_name":"RenamedCard"}' --check
```

Contract:

- `MODULE` may be an importable module or a Python file path.
- `OBJECT` may be a function, a `codemods.codemod.Codemod` subclass/instance,
  or an object exposing callable `execute`.
- Callable targets receive `codebase` and optionally `arguments`.
- `--check` and `--write` are mutually exclusive.
- One of `--check` or `--write` is required.
- `--check` must never mutate the target repo, including when a codemod calls
  `codebase.commit()`.
- `--write` may mutate the target repo and should print a clear success or
  no-op message.

### Backend And Fallback Semantics

Backend selection is shared by `parse`, `run`, and `transform`.

| Request | Rust unavailable | Unsupported Rust API during transform |
| --- | --- | --- |
| `--backend python` | Not relevant | Not relevant |
| `--backend rust --fallback error` | Exit non-zero | Exit non-zero |
| `--backend rust --fallback python` | Fall back to Python | Fall back to Python graph if possible |
| `--backend auto --fallback python` | Fall back to Python | Fall back to Python graph if possible |

Use explicit strict Rust examples when benchmarking or proving the Rust backend:

```bash
uvx graph-sitter parse ./repo --backend rust --fallback error --format json
uvx graph-sitter transform ./codemod.py:run ./repo --backend rust --fallback error --check
```

Use resilient examples in public docs while parity is still incomplete:

```bash
uvx graph-sitter parse ./repo --backend auto --fallback python --format summary
uvx graph-sitter transform ./codemod.py:run ./repo --backend auto --fallback python --check
```

### Doctor

Primary forms:

```bash
uvx graph-sitter doctor
uvx graph-sitter doctor --json
uvx graph-sitter doctor --backend rust --language python --json
uvx graph-sitter doctor --backend rust --language typescript --json
```

Contract:

- `doctor --json` is machine-readable and suitable for setup docs, CI, and
  skills.
- `--backend python` reports package, platform, parser dependency, and Rust
  extension availability without requiring the Rust extension.
- `--backend rust` additionally runs a generated tiny-repo strict Rust parse
  smoke with `rust_fallback=error` and exits non-zero if the extension is
  unavailable or the smoke fails.
- The command should not inspect or mutate the user's target repo.

## Branch-Built Wheel Proof

Already proven on the `rust-rewrite` branch:

- `rust-rewrite/tools/check_wheel_rust_backend.sh` builds a wheel, creates a
  clean uv cache, and executes the installed console script through
  `uvx --python "$PYTHON_VERSION" --from dist/<wheel>.whl graph-sitter`.
- The wheel smoke asserts the archive includes both `graph_sitter_py` and
  `codemods/codemod.py`.
- The installed wheel runs `graph-sitter --help`.
- The installed wheel parses a tiny Python repo with
  `--backend python --format json`.
- The installed wheel parses the same repo with
  `--backend rust --fallback error --format json`.
- The installed wheel parses a tiny TypeScript repo with
  `--language typescript --backend rust --fallback error --format json`.
- The installed wheel runs a file-based import-path transform in strict Rust
  mode with `--check`, exits `1`, reports produced changes, and leaves the
  target repo unchanged.
- The installed wheel runs the same transform in strict Rust mode with
  `--write`, reports applied changes, and mutates the target repo.
- The installed wheel runs a TypeScript import-path transform in strict Rust
  mode with `--check` and `--write`, proving a tiny exported function rename
  from the packaged artifact.
- `rust-rewrite/tools/check_wheel_pinned_python_repo.py` builds or accepts a
  wheel, installs it through `uvx --from dist/<wheel>.whl`, parses pinned
  Airflow `2.10.5` in strict Rust Python mode, and compares the summary counts
  with the committed compact golden snapshot. It can also run
  `--compare-python-backend` and `--run-transform-proof` for installed-wheel
  Python-vs-Rust performance and real Airflow transform validation.
- On 2026-06-19, the Airflow wheel gate measured strict Rust parse at 4.913s
  and 487.0 MB sampled process-tree RSS versus installed-wheel Python at
  48.242s and 5429.3 MB, a 9.818x parse-elapsed and 11.148x sampled-RSS
  improvement. Its transform proof renamed `__getattr__` to
  `__getattr_wheel_proof__` in `airflow/__init__.py`, touched only that file,
  and measured 5.920s with 500.1 MB sampled process-tree RSS.
- `rust-rewrite/tools/check_wheel_pinned_typescript_repo.py` builds or accepts a
  wheel, installs it through `uvx --from dist/<wheel>.whl`, parses pinned
  Next.js `v15.0.0` in strict Rust TypeScript mode, and compares the summary
  counts with the committed compact golden snapshot.
- The same Next.js wheel gate can run with `--compare-python-backend` to sample
  installed-wheel Python and Rust process-tree RSS. On 2026-06-19, the
  branch-built wheel parsed pinned Next.js with strict Rust in 10.352s and
  537.5 MB sampled RSS versus the installed-wheel Python backend at 57.956s and
  4505.6 MB, a 5.598x parse-elapsed and 8.383x sampled-RSS improvement.
- The Next.js wheel gate can also run with `--run-transform-proof` to clone the
  pinned checkout, run strict Rust `graph-sitter transform ... --write` through
  `uvx --from`, add an import to `app-router-announcer.tsx`, rename
  `AppRouterAnnouncer` to `AppRouterAnnouncerWheelProof`, rewrite the importing
  usage in `app-router.tsx`, and assert only those two files changed. On
  2026-06-19, that installed-wheel transform ran in 11.834s with 525.8 MB
  sampled process-tree RSS.
- `.github/workflows/rust-rewrite-extension.yml` runs this wheel smoke on Linux
  and macOS for Python 3.12 and 3.13.

This is an artifact-level branch proof. It is stronger than checkout-local
tests because it uses a built wheel installed through `uvx --from`. It is not
yet a published-package proof because it does not install from PyPI or the final
release index.

Not yet proven by the branch-built wheel smokes:

- `uvx graph-sitter ...` with no `--from` after upload to the package index.
- `uvx --from graph-sitter==<version> graph-sitter ...` against an uploaded
  release or pre-release artifact.
- Full codemod diff parity between Python and Rust backends from an installed
  wheel.
- Skill installation and invocation against the published package.

## Release Artifact Checklist

A release is ready to advertise `uvx graph-sitter ...` only after these checks
pass against uploaded artifacts, not just branch-built wheels.

### Build And Publish Candidate

- [ ] Build CPython 3.12 and 3.13 wheels for the supported release platforms.
- [ ] Build and inspect the sdist, if one will be published.
- [ ] Verify every wheel contains `graph_sitter_py` and `codemods/codemod.py`.
- [ ] Verify Python-backend imports remain optional-Rust safe.
- [ ] Upload to a pre-release index or publish a pre-release version.

### Published-Package Smokes

Use exact-version commands for release gates:

```bash
uvx --python 3.13 --from graph-sitter==<version> graph-sitter --help
uvx --python 3.13 --from graph-sitter==<version> graph-sitter parse ./tiny-python --language python --backend python --format json
uvx --python 3.13 --from graph-sitter==<version> graph-sitter parse ./tiny-python --language python --backend rust --fallback error --format json
uvx --python 3.13 --from graph-sitter==<version> graph-sitter parse ./tiny-ts --language typescript --backend rust --fallback error --format json
uvx --python 3.13 --from graph-sitter==<version> graph-sitter transform ./rename.py:rename ./tiny-python --language python --backend rust --fallback error --check
uvx --python 3.13 --from graph-sitter==<version> graph-sitter transform ./rename.py:rename ./tiny-python --language python --backend rust --fallback error --write
```

Then verify the default user-facing spelling:

```bash
uvx --python 3.13 graph-sitter --help
uvx --python 3.13 graph-sitter parse ./tiny-python --language python --backend auto --fallback python --format summary
```

### Large-Repo Gates

- [ ] Run pinned Airflow parse from the published package with
  `--backend rust --fallback error --format json`.
- [ ] Run pinned Next.js parse from the published package with
  `--backend rust --fallback error --format json`.
- [ ] Record latency and max RSS versus the branch's Python-backend baselines.
- [ ] Run at least one Python codemod and one TypeScript codemod from the
  published package and assert exact file diffs.
- [ ] Compare Python-backend and Rust-backend transform diffs for those codemods
  where both backends are expected to support the same API surface.

### Documentation And Skill Gates

- [ ] Update setup docs to prefer `uvx --python 3.13 graph-sitter ...`.
- [ ] Update the skill to pin a known-good package version until the default
  latest release is trusted.
- [ ] Add a troubleshooting section for Rust extension import failures.
- [ ] Document when to use `--backend rust --fallback error` versus
  `--backend auto --fallback python`.
- [ ] Document that `transform` requires explicit `--check` or `--write`.

## Skill-Facing Invocation Guidance

Skill examples should be conservative, exact, and machine-readable.

Recommended parse pattern:

```bash
uvx --python 3.13 --from graph-sitter==<version> graph-sitter parse <repo> --language <python|typescript> --backend auto --fallback python --format json
```

Recommended Rust proof pattern:

```bash
uvx --python 3.13 --from graph-sitter==<version> graph-sitter parse <repo> --language <python|typescript> --backend rust --fallback error --format json
```

Recommended transform pattern:

```bash
uvx --python 3.13 --from graph-sitter==<version> graph-sitter transform <transform.py>:<object> <repo> --language <python|typescript> --backend auto --fallback python --arguments '<json-object>' --check
uvx --python 3.13 --from graph-sitter==<version> graph-sitter transform <transform.py>:<object> <repo> --language <python|typescript> --backend auto --fallback python --arguments '<json-object>' --write
```

Skill rules:

- Use `--format json` for parse commands and parse JSON fields instead of
  scraping summary text.
- Pin `--python 3.13` while package metadata remains `>=3.12,<3.14`.
- Pin the package version with `--from graph-sitter==<version>` until release
  confidence is high enough to use latest.
- Use `--backend rust --fallback error` only for performance, CI, or parity
  proofs where silent fallback would invalidate the result.
- Use `--backend auto --fallback python` for productivity flows while Rust
  parity is incomplete.
- Always run transforms with `--check` before `--write` unless the user has
  explicitly requested direct mutation.
- Prefer import-path `transform` for one-shot skill workflows because it does
  not require `.codegen/codemods` registration.
- Prefer registered `run` for repository-owned codemods that already live under
  `.codegen/codemods`.
- Treat non-zero `--check` exit status as expected when a transform would
  produce changes.

## Multi-Agent Checklist

### Contract And Docs

- [x] Define the public `uvx graph-sitter ...` parse/run/transform command
  shape. owner: CLI/distribution agent.
- [x] Record branch-built wheel proof versus published-package validation.
  owner: CLI/distribution agent.
- [x] Reconcile public CLI docs with this roadmap. owner: delegated-worker.
  Result: `docs/cli/run.mdx` now documents explicit path/check/write/uvx
  usage, `docs/cli/transform.mdx` documents one-shot import-path transforms,
  and the CLI overview/navigation links the parse/run/transform taxonomy.
- [ ] Update skill docs to use explicit `--check` or `--write` in every
  transform example. owner: skill/docs agent.
- [ ] Replace remaining user-facing "codegen function" copy in
  `graph-sitter run --help` with Graph-sitter/codemod wording. owner: CLI UX
  agent.
- [ ] Add a docs release note that distinguishes branch-built wheel proof from
  published-package proof. owner: release/docs agent.
- [x] Add `graph-sitter doctor` for setup and skill diagnostics. owner: codex.
  Result: `doctor --json` reports Python/package/platform/parser dependency
  readiness, Rust extension status, and an optional generated strict Rust parse
  smoke for Python or TypeScript.

### Parse Implementation

- [x] Add repeatable `--subdir` support to `graph-sitter parse`. owner: codex.
  Result: parse accepts repeated repository-relative or in-repo absolute
  subdirectory/file filters, threads them through `ProjectConfig`, reports the
  selected `subdirectories` in JSON, and has focused Python-backend CLI tests.
- [ ] Add `--output` for JSON output files once the JSON schema is stable.
  owner: CLI implementation agent.
- [ ] Decide whether `jsonl` belongs in v1 or should wait for a richer graph
  export command. owner: CLI/distribution agent.
- [ ] Version the parse JSON schema or document its stability policy. owner:
  CLI/contracts agent.
- [ ] Add `--backend auto` unit coverage for unavailable Rust fallback and
  selected-backend disclosure. owner: test agent.
- [x] Add installed-wheel TypeScript strict Rust parse smoke. owner: codex.
  Result: `check_wheel_rust_backend.sh` now builds a tiny TypeScript repo and
  asserts strict Rust parse counts through `uvx --from dist/<wheel>.whl`.

### Transform Implementation

- [x] Add uvx-level import-path transform smokes from a built wheel for both
  `--check` and `--write`. owner: codex. Result:
  `check_wheel_rust_backend.sh` runs a file-based transform from the built wheel
  in strict Rust mode, proves `--check` reports a diff without mutating the
  target repo, then proves `--write` mutates the target repo.
- [x] Prove `transform` requires explicit mode and rejects `--check --write`.
  owner: codex. Result: focused transform CLI tests cover both errors.
- [ ] Add Rust-backend transform tests that either pass fully or fail/fallback
  according to `--fallback`. owner: parity/test agent.
- [ ] Add a no-op transform test for `--check` returning exit zero and
  "No changes would be produced". owner: CLI test agent.
- [x] Add TypeScript installed-wheel transform smoke. owner: codex. Result:
  `check_wheel_rust_backend.sh` now proves a tiny TypeScript function rename
  through `transform --check` and `transform --write` from the installed wheel.
- [ ] Decide whether `run` should eventually require explicit `--check` or
  `--write` in a major release. owner: CLI/contracts agent.

### Packaging And Release

- [x] Prove built wheels include `codemods` and `graph_sitter_py` in clean uv
  environments. owner: codex. Result: `check_wheel_rust_backend.sh` asserts
  both wheel contents and imports the CLI from a clean `uvx --from
  dist/<wheel>.whl` environment.
- [x] Add Linux and macOS wheel uvx smokes for Python 3.12 and 3.13. owner:
  codex. Result: `.github/workflows/rust-rewrite-extension.yml` runs
  `check_wheel_rust_backend.sh` across the supported Python/OS matrix.
- [x] Add artifact-level smoke for `--backend rust --fallback error` before
  advertising Rust-backed uvx parse. owner: codex. Result: branch-built wheel
  CI runs strict Rust parse and strict Rust transform smokes from the installed
  artifact.
- [ ] Add published-package release checklist requiring `uvx graph-sitter
  --help`, parse, and transform against the uploaded artifact. owner: release
  agent.
- [ ] Decide long-term Rust extension import namespace: keep top-level
  `graph_sitter_py` or move to `graph_sitter._rust`. owner: packaging/API
  agent.
- [ ] Decide whether Windows wheels are in or out for the first public Rust
  backend release. owner: release agent.

### Correctness And Benchmarks

- [ ] Add pinned large Python repo `uvx parse --backend rust --fallback error`
  benchmark from a published-package artifact. owner: benchmark agent.
- [ ] Add pinned large TypeScript repo `uvx parse --backend rust --fallback
  error` benchmark from a published-package artifact. owner: benchmark agent.
- [ ] Add pinned codemod fixtures that assert file diffs, not just graph counts.
  owner: codemod parity agent.
- [ ] Compare Rust and Python backend transform diffs for the same pinned
  codemods. owner: codemod parity agent.
- [ ] Define correctness language for docs: current behavior is tested and
  improving, but not claimed correct for all codebases. owner: docs/contracts
  agent.

## Open Decisions For The Integrator

- When should `parse` default from `--backend python` to `--backend auto`?
- Should `run` require explicit `--check` or `--write` in the first major
  release after the Rust backend ships, or keep default write forever?
- Is `graph_sitter_py` acceptable as the public wheel extension namespace for
  the first release, or should the move to `graph_sitter._rust` happen before
  publishing Rust-backed wheels?
- Do first public Rust-backed wheels need Windows support, or is Linux/macOS
  enough for the initial release?
- Should `parse --format json` be versioned before docs and skills depend on
  it?

## Blockers

- Public `uvx graph-sitter` availability still requires a released package or
  explicit `uvx --from` source/artifact usage.
- Published-package validation is still required before docs should imply that
  `uvx graph-sitter ...` works from the package index.
- Branch-built wheel smokes now cover Python and TypeScript parse/transform,
  plus pinned Airflow/Next.js large-repo gates; published-package validation is
  still open.
- Rust-backed transformations are only fully ready when the transform APIs used
  by codemods either work through Rust handles or fall back according to
  `--fallback`.
- Defaulting to `--backend auto` should wait until P0 parity, published-package
  artifact smokes, and large-repo gates prove the Rust backend is the safer
  default for supported languages.
