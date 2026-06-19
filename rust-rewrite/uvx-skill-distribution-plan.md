# `uvx graph-sitter` And Skill Distribution Plan

## Purpose

This document is the release-facing plan for the future one-shot command and
distributable Codex skill:

```bash
uvx graph-sitter ...
```

The command should let a user or agent parse a codebase, inspect the generated
graph, and run transformations without cloning Graph-sitter or hand-wiring a
local development environment. The skill should teach Codex agents when and how
to use that command, when to use the Python API directly, and how to validate
large-repo or codemod claims.

Existing planning inputs:

- `rust-rewrite/uvx-command-roadmap.md`
- `rust-rewrite/uvx-cli-plan.md`
- `rust-rewrite/skill-distribution-plan.md`
- `rust-rewrite/skill-prototype/graph-sitter/`

Those files are useful source material, but this plan should stay conservative:
published-package claims are only true after PyPI wheels, clean `uvx` smokes,
and release validation have passed.

## Target UX

### Parse

Canonical command:

```bash
uvx graph-sitter parse [PATH]
```

Expected options:

```bash
uvx graph-sitter parse [PATH] --language auto|python|typescript
uvx graph-sitter parse [PATH] --backend auto|rust|python
uvx graph-sitter parse [PATH] --fallback error|python
uvx graph-sitter parse [PATH] --format summary|json
uvx graph-sitter parse [PATH] --subdir src --subdir packages/app
uvx graph-sitter parse [PATH] --output graph-sitter-index.json
```

Target behavior:

- `PATH` defaults to the current directory.
- The command is read-only.
- The command does not require `gs init`, `.codegen`, a daemon, or an active
  historical session.
- `--format summary` is optimized for humans and may change copy over time.
- `--format json` is the stable agent/CI contract and includes the requested
  backend, actual backend, language, elapsed time, selected subdirectories,
  file/symbol/import/export/reference/dependency counts, parse errors, and Rust
  fallback/error reason.
- Repeatable `--subdir` should be preferred by skills when the requested task is
  scoped to known folders in a large repo.
- `--backend rust --fallback error` is strict: use the Rust extension or fail
  with a clear message.
- `--backend auto --fallback python` is the eventual default: prefer Rust for
  supported Python and JS/TS repositories, fall back to Python for unsupported
  surfaces, and disclose the actual backend in JSON.
- Until release gates pass, public examples should pin the backend explicitly
  rather than implying universal Rust coverage.

Examples:

```bash
uvx graph-sitter parse ./airflow --language python --backend auto --fallback python
uvx graph-sitter parse ./next.js --language typescript --backend rust --fallback error --format json
```

### Transform

Ad hoc import-path transforms:

```bash
uvx graph-sitter transform MODULE:OBJECT [PATH] --check
uvx graph-sitter transform MODULE:OBJECT [PATH] --write
```

Registered codemods:

```bash
uvx graph-sitter run LABEL [PATH] --check
uvx graph-sitter run LABEL [PATH] --write
```

Expected options:

```bash
uvx graph-sitter transform ./codemod.py:rename ./repo --arguments '{"name":"new_name"}' --check
uvx graph-sitter run rename-symbol ./repo --backend auto --fallback python --diff-preview 200 --write
```

Target behavior:

- `transform MODULE:OBJECT` is the preferred one-shot path for agents and CI
  because it does not require `.codegen/codemods`.
- `run LABEL` remains the path for registered workspace codemods.
- `--check` runs in a temporary copied repository, prints a diff, leaves the
  target unchanged, and exits non-zero when changes would be produced.
- `--write` applies changes to the target repository.
- New docs and skill examples should always show `--check` before `--write`.
- Current `run` compatibility may continue writing by default, but the
  long-term `uvx` story should make write intent explicit.
- Transform examples must include post-run validation: `git diff`, focused
  tests, or the target repository's standard check command.

### Setup And Init

The setup/init story should support two different workflows.

One-shot validation:

```bash
uvx graph-sitter doctor
uvx graph-sitter doctor --json
uvx graph-sitter doctor --backend rust --language python --json
uvx graph-sitter doctor --backend rust --language typescript --json
```

Target behavior:

- Check Python version compatibility.
- Report package version, console script, optional Rust extension availability,
  supported languages, platform tag, and fallback mode guidance.
- In `--backend rust` mode, perform a tiny strict Rust parse smoke and fail
  clearly if the platform wheel lacks the extension.

Workspace codemod setup:

```bash
uvx graph-sitter init [PATH]
uvx graph-sitter init [PATH] --codemods
uvx graph-sitter init [PATH] --skill-notes
```

Target behavior:

- Keep `init` focused on repository-local codemod scaffolding, not global
  package setup.
- Create or validate `.codegen/codemods` only when requested or when the user is
  preparing registered codemods.
- Never require `init` before `parse` or import-path `transform`.
- `--skill-notes` can print the recommended Codex skill invocation and
  validation commands without installing anything globally.

## Packaging Prerequisites

### PyPI And `uvx`

- Publish the distribution as `graph-sitter`.
- Keep `graph-sitter = "graph_sitter.cli.cli:main"` as the canonical console
  script.
- Keep `gs = "graph_sitter.cli.cli:main"` as a compatibility alias for at
  least one release line.
- Ensure `uvx graph-sitter --help`, `uvx graph-sitter parse ...`, and
  `uvx graph-sitter transform ...` work in a clean environment with no checkout
  on `PYTHONPATH`.
- Pin or bound parser/runtime dependencies tightly enough that clean `uvx`
  resolution cannot select incompatible tree-sitter or JavaScript runtime
  wheels.
- Keep package import side effects light: importing the Python shell must not
  require the Rust extension unless the user selected the Rust backend.

### Python Shell And Rust Extension

- Python remains the public API, codemod authoring language, and compatibility
  shell.
- Rust owns the compact parse/index/resolution data path when the selected
  backend supports the requested language and API surface.
- The PyO3 extension should be bundled into platform wheels and imported as the
  optional Rust backend.
- `--backend python` must work even when the extension is absent.
- `--backend rust --fallback error` must fail rather than silently degrade.
- `--backend rust --fallback python` and `--backend auto --fallback python` may
  degrade, but JSON output must state the actual backend and error reason.
- Unsupported Rust-backed APIs should fail explicitly in strict mode rather
  than accidentally materializing the old Python graph.

### Wheel And Platform Concerns

- Build and test wheels for supported Python versions before PyPI release.
  Current branch assumptions are Python 3.12 and 3.13.
- Required release wheel matrix should include at least:
  - macOS arm64
  - macOS x86_64
  - Linux x86_64 manylinux
  - Linux aarch64 manylinux, if CI capacity is available
- Windows support should be declared either supported with wheels and tests or
  explicitly deferred.
- Mark wheels platform-specific when they contain `graph_sitter_py`.
- Source distributions must include the Rust crates, Cargo metadata, grammar
  dependencies, and build hook files needed to build the extension.
- If a source build cannot compile Rust, installation should still make the
  Python backend usable or fail with a clear build-time message. Do not publish
  an ambiguous package that installs but cannot run `graph-sitter --help`.

## Skill Packaging

The distributable Codex skill should be a small operating guide, not a copy of
the product docs.

Recommended artifact:

```text
graph-sitter/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── cli.md
    ├── codemods.md
    └── rust-backend.md
```

Recommended trigger:

```yaml
---
name: graph-sitter
description: Use Graph-sitter to parse, query, analyze, and transform Python, TypeScript, JavaScript, and React codebases. Trigger when Codex needs semantic codebase graphs, dependency/import/reference analysis, codemod execution, large-repo Rust-backed parsing, or `uvx graph-sitter ...` workflows.
---
```

The skill should document these commands:

```bash
uvx graph-sitter parse <repo> --language auto --backend auto --fallback python --format json
uvx graph-sitter parse <repo> --language typescript --backend rust --fallback error --format json
uvx graph-sitter transform ./codemod.py:run <repo> --check
uvx graph-sitter transform ./codemod.py:run <repo> --write
uvx graph-sitter run <label> <repo> --check
uvx graph-sitter doctor --backend rust
```

The skill should also document when to use the Python API directly:

```python
from graph_sitter import Codebase

codebase = Codebase("/path/to/repo")
symbol = codebase.get_function("main")
print([dependency.name for dependency in symbol.dependencies])
```

Skill validation expectations:

- Run the Codex skill validator against the final skill folder.
- In a clean agent session, validate that the skill loads only the references it
  needs for a parse task.
- In a clean agent session, validate that a mutation task runs `--check` before
  `--write`.
- Run a local command smoke from the skill's documented commands before
  release.
- Keep wording precise: say "supported Rust-backend subset" and "selected
  pinned large-repo parity", not "fully correct".

## Staged Implementation And Test Plan

### Stage 1: Command Contract

- [ ] Freeze the JSON contract for `graph-sitter parse --format json`.
- [x] Add `graph-sitter doctor` with Python, package, platform, parser
  dependency, Rust extension, and optional strict Rust parse-smoke diagnostics.
  Result: `doctor --json` is machine-readable; `--backend rust` generates a
  tiny temporary repo and fails if the Rust extension or strict Rust parse is
  unavailable.
- [ ] Decide whether `graph-sitter init` remains historical session setup,
  codemod scaffolding, or both.
- [ ] Update help text so `graph-sitter`, not legacy Codegen naming, is the
  visible product surface.
- [ ] Add CLI tests that assert `parse`, `transform`, `run`, `doctor`, and
  `init` help output stays aligned with docs.

### Stage 2: Distribution Artifacts

- [ ] Build platform wheels with the Rust extension included.
- [ ] Build an sdist and verify either a successful local Rust build or a clear
  documented fallback/failure mode.
- [ ] Run clean `uvx --from dist/<wheel>.whl graph-sitter --help` for every
  supported wheel.
- [ ] Run clean `uvx --from dist/<wheel>.whl graph-sitter parse` for Python and
  TypeScript fixtures with `--backend python`.
- [ ] Run clean `uvx --from dist/<wheel>.whl graph-sitter parse` for Python and
  TypeScript fixtures with `--backend rust --fallback error`.
- [ ] Run clean `uvx --from dist/<wheel>.whl graph-sitter transform` with
  `--check` and `--write` on Python and TypeScript fixtures.

### Stage 3: Published-Package Proof

- [ ] Publish a pre-release package or TestPyPI artifact.
- [ ] Validate `uvx --from graph-sitter==<version> graph-sitter --help`.
- [ ] Validate `uvx --from graph-sitter==<version> graph-sitter parse` on a
  small Python repo and a small TypeScript repo.
- [ ] Validate strict Rust parse from the published artifact on supported
  platforms.
- [ ] Validate strict Rust transform from the published artifact on supported
  platforms.
- [ ] Publish docs only after the package command examples have been replayed
  from the published artifact, not only from a local checkout.

### Stage 4: Skill Release

- [ ] Promote `rust-rewrite/skill-prototype/graph-sitter/` into the chosen
  distribution location.
- [ ] Update skill references so commands match the published package, not
  branch-only behavior.
- [ ] Run skill validation against the final folder.
- [ ] Forward-test the skill with one read-only parse task.
- [ ] Forward-test the skill with one codemod `--check` task and one `--write`
  task on a disposable repo.
- [ ] Package the skill with release notes that state supported languages,
  backend status, and known limitations.

### Stage 5: Large-Repo Proof

- [ ] Run pinned Airflow parse and semantic parity proof from the installed
  wheel or published package.
- [ ] Run pinned Next.js parse and semantic parity proof from the installed
  wheel or published package.
- [ ] Run pinned Airflow and Next.js codemod proof from the installed wheel or
  published package.
- [ ] Record wall time, max RSS, current RSS, repo commit, platform, Python
  version, package version, and backend/fallback mode in reports.
- [ ] Decide which large-repo checks are release gates and which remain
  scheduled/manual due to runtime.

## Risks And Open Questions

- [ ] Large repo memory: compact Rust construction is much smaller, but broad
  Python-side handle or JSON materialization can still dominate memory. The
  skill and docs should teach targeted lookups for large repos.
- [ ] Correctness: parity with the old Python backend is not the same thing as
  absolute semantic correctness. Keep correctness language scoped to tested
  fixtures, supported subsets, and pinned repo probes.
- [ ] Codemods: read-only graph APIs have broader proof than mutations. Keep
  codemod release gates explicit for Python and JS/TS, and always require
  check-mode validation before write-mode examples.
- [ ] JS/TS: Next.js is the right large-repo proof target, but TypeScript syntax,
  type-only edges, namespace exports, JSX, and monorepo config resolution need
  ongoing pinned coverage.
- [ ] Benchmark proof: public performance claims must include repo commit,
  platform, Python version, package source, backend, fallback mode, wall time,
  RSS metric, and whether broad caches were materialized.
- [ ] Platform wheels: Rust-backed `uvx` is only as real as the wheel matrix.
  Unsupported platforms need honest fallback language.
- [ ] Default backend: `--backend auto` should not become the documented default
  until published-package smokes, correctness gates, codemod gates, and
  large-repo benchmark gates pass.
- [ ] Skill install path: decide whether the skill ships inside the repository,
  as a release asset, through a marketplace, or through a future `uvx
  graph-sitter skill install` helper.
