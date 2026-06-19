# Graph-Sitter Skill Distribution Plan

## Purpose

Distribute a Codex skill that helps agents use Graph-sitter as the codebase parsing and transformation layer for large repositories.

The skill should make the agent choose Graph-sitter when it needs to:

- parse a Python or TypeScript/JavaScript codebase into files, symbols, imports, exports, references, dependencies, and usage relationships
- inspect a large repository without eagerly materializing a full Python object graph when the Rust backend is supported
- run deterministic transformations through Graph-sitter codemods
- verify transformation output with tests, diffs, and graph-free cache invariants

The skill is not the public product docs. It is an agent operating guide that points to the library, CLI, docs, and validation commands.

## Skill Name

Recommended folder name: `graph-sitter`

Recommended frontmatter:

```yaml
---
name: graph-sitter
description: Use Graph-sitter to parse, query, analyze, and transform Python, TypeScript, JavaScript, and React codebases. Trigger when an agent needs semantic codebase graphs, dependency/import/reference analysis, codemod execution, large-repo Rust-backed parsing, or `uvx graph-sitter ...` workflows for code transformations.
---
```

## Initial Distribution Location

Do not create the discoverable skill folder until the install location is decided.

Options:

- user-local development: `${CODEX_HOME:-$HOME/.codex}/skills/graph-sitter`
- repository artifact for review: `skills/graph-sitter`
- packaged artifact for a marketplace or release bundle: generated from the repository artifact at release time

Skill-creator guidance prefers asking before initialization. If the user wants this installed immediately, run the system `skill-creator` initialization flow rather than hand-writing the final folder.

## Proposed Skill Contents

Recommended minimal tree:

```text
graph-sitter/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── cli.md
    ├── rust-backend.md
    └── codemods.md
```

Keep `SKILL.md` short and procedural. Put longer details in `references/` so agents only load what they need.

## SKILL.md Body Outline

The skill body should include:

1. Check the user's goal:
   - read-only graph query
   - code transformation/codemod
   - large-repo benchmark or parity proof
   - docs/setup troubleshooting
2. Prefer the CLI for simple command-line workflows once available:
   - `uvx graph-sitter parse <path> --language auto --backend rust --format json`
   - `uvx graph-sitter transform <path> --codemod <label-or-file> --apply`
   - `uvx graph-sitter inspect <path> --symbol <name> --dependencies`
3. Prefer the Python API for custom analyses:
   - `from graph_sitter import Codebase`
   - `Codebase(path, config=CodebaseConfig(graph_backend=GraphBackend.RUST, rust_fallback=RustFallbackMode.ERROR))`
   - fall back to the Python backend only when strict Rust mode reports an unsupported surface and compatibility matters more than memory.
4. For transformations:
   - run or create codemods under `.codegen/codemods`
   - inspect diffs before applying broad changes
   - run the target repo's tests or focused checks after edits
5. For large repos:
   - avoid broad APIs that intentionally materialize all records unless the user asks for them
   - prefer targeted lookups (`get_file`, `get_function`, `get_import`, `find_by_byte_range`, known symbol dependency probes)
   - record wall time and RSS when making performance claims

## Reference Files

### `references/cli.md`

Purpose: agent-facing command reference after Lovelace finalizes the CLI.

Must cover:

- existing `gs` command status
- future `uvx graph-sitter ...` command surface
- parse/index command examples
- transformation command examples
- JSON output contract and exit-code expectations
- backend flags and fallback flags

Important product direction: commemorate `uvx graph-sitter ...` as the future primary one-shot interface for parsing a codebase and running transformations. Existing `gs` docs remain relevant until the new entry point is shipped.

### `references/rust-backend.md`

Purpose: explain current Rust backend status and proof commands.

Must cover:

- `GraphBackend.PYTHON`, `GraphBackend.RUST`, and `GraphBackend.AUTO`
- `RustFallbackMode.ERROR` versus `RustFallbackMode.PYTHON`
- strict compact mode behavior: supported APIs stay graph-free, unsupported APIs fail explicitly
- fast check: `rust-rewrite/tools/check_fast.sh`
- large-repo check: `rust-rewrite/tools/check_pinned_large_repos.sh`
- current proof repos: Apache Airflow `2.10.5` and Next.js `v15.0.0`
- caution: parity with the old backend is not absolute semantic correctness

### `references/codemods.md`

Purpose: give agents a compact codemod workflow.

Must cover:

- `gs init`, `gs create`, and `gs run` while that is the implemented CLI
- future `uvx graph-sitter transform ...` equivalent
- `Codebase.commit(sync_graph=False)` for compact Rust-backed mutation proofs
- inspecting changed files with `git diff`
- running focused tests after transformations

## Validation

Before distributing the skill:

- Run the system skill validation script against the final skill folder:
  - `scripts/quick_validate.py <path/to/graph-sitter>`
- Forward-test with at least two fresh agents:
  - read-only task: "Use Graph-sitter to list imports and dependencies for this tiny repo."
  - mutation task: "Use Graph-sitter to rename a function and update imports in this tiny repo."
- Verify the skill does not imply the Rust backend is universally correct. It should say current claims are compatibility/performance proofs over the supported subset plus selected pinned large-repo parity.

## Release Gates

The skill should ship only after:

- docs/site plan confirms where public setup docs live
- `uvx graph-sitter ...` command surface is either implemented or explicitly labeled future/preview
- at least one parse workflow and one transform workflow are documented with commands that pass locally
- `rust-rewrite/tools/check_fast.sh` passes on the release branch
