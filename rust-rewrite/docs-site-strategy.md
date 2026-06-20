# Graph-sitter Docs, Landing, Vercel, And Skill Strategy

## Recommendation

Keep the product docs and the landing page as separate surfaces:

- `docs/`: Mintlify documentation source of truth.
- `site/`: Vercel-hosted Next.js landing page.
- `rust-rewrite/skill-prototype/graph-sitter/`: draft Codex skill artifact until the package and docs are release-ready.

The landing page should explain Graph-sitter in one screen and route users to the docs. The docs should carry setup, CLI, API, Rust backend, JS/TS, codemod, correctness, and benchmark details. This avoids coupling generated API reference pages and long-form guides to a small marketing app.

If the team later decides "docs site on Vercel" means moving docs rendering off Mintlify, treat that as a separate migration. The likely path would be a docs app under `site/docs` or `apps/docs` using MDX, with a scripted import from `docs/`. Do not start there unless Mintlify becomes a blocker.

## Current Repo Signals

- [x] `docs/mint.json` configures the Mintlify docs tree.
- [x] `docs/README.md` already documents local Mintlify validation.
- [x] `site/` is a Next.js app with `npm run dev`, `npm run build`, and checked-in `package-lock.json`.
- [x] `site/app/page.tsx` already positions Graph-sitter as a Python shell with a compact Rust backend and future `uvx graph-sitter ...` command surface.
- [x] No repo-level `vercel.json`, `site/vercel.json`, `.vercel/`, or `site/.vercel/` is checked in.
- [x] Vercel CLI is available locally: `Vercel CLI 54.7.1`.
- [x] Vercel CLI auth is present for user `jayhack`.
- [x] `pyproject.toml` already exposes both `gs` and `graph-sitter` console scripts.
- [x] `rust-rewrite/uvx-command-roadmap.md`, `rust-rewrite/uvx-cli-plan.md`, and `rust-rewrite/uvx-skill-distribution-plan.md` already commemorate `uvx graph-sitter ...` as the target one-shot interface.

## Information Architecture

Recommended public URLs:

```text
https://graph-sitter.com       -> Vercel landing app rooted at site/
https://www.graph-sitter.com   -> Vercel redirect or alias to the apex
https://docs.graph-sitter.com  -> Mintlify docs rooted at docs/
```

Landing page responsibilities in `site/`:

- one-sentence definition: codebase graphs for analysis and codemods
- Python API example
- parse, graph, transform capabilities
- Python shell plus Rust backend architecture
- cautious `uvx graph-sitter ...` preview
- links to docs and GitHub

Docs responsibilities in `docs/`:

- install and setup
- parse command and JSON output
- registered codemods through `run`
- ad hoc import-path transforms through `transform`
- Rust backend status, fallback modes, and release gates
- Python, JavaScript, TypeScript, and React support
- correctness and parity methodology
- large-repo benchmark methodology and results
- generated API reference
- Codex skill installation and usage once published

## Accuracy Contract For Docs

Setup docs must be explicit about three workflows:

```bash
# local source checkout
uv run graph-sitter doctor
uv run graph-sitter parse . --backend python --format json

# released package, after PyPI and wheel gates pass
uvx graph-sitter doctor
uvx graph-sitter parse . --language auto --backend auto --fallback python --format json

# branch-built wheel validation before public release
uvx --from dist/<wheel>.whl graph-sitter parse . --backend rust --fallback error --format json
```

Parsing docs must specify:

- `PATH` defaults and whether `.codegen` is required.
- `--language auto|python|typescript` behavior.
- `--backend python|rust|auto` behavior.
- `--fallback error|python` semantics.
- `--subdir` behavior for large repos.
- summary output versus JSON output.
- JSON schema version and stable fields.

Transform and codemod docs must specify:

- `transform MODULE:OBJECT PATH --check|--write` for one-shot transforms.
- `run LABEL PATH --check|--write` for registered `.codegen/codemods` workflows.
- `--check` runs in a copied temporary repo and leaves the target unchanged.
- `--write` mutates the target.
- examples should show `--check` before `--write`.
- post-run validation should include `git diff` and focused target tests.

Rust backend docs must specify:

- Python remains the authoring shell and compatibility path.
- Rust is the compact parse/index backend for supported surfaces.
- strict mode is `--backend rust --fallback error`.
- fallback mode must disclose the actual backend and reason.
- unsupported Rust-backed APIs should fail explicitly in strict mode.
- public claims should say "supported subset" or "selected pinned large-repo parity" until correctness work proves more.

JS/TS docs must specify:

- supported language selector is currently `typescript` for TS/JS/React flows unless the CLI adds a separate `javascript` selector.
- large-repo proof target is pinned Next.js.
- TS docs need one parse example, one read-only graph query, one checked transform, and one write transform.
- React/JSX support should be described by tested AST/API behavior, not broad ecosystem claims.

Benchmark docs must specify:

- exact repo and commit/tag.
- backend, language, command, Python version, platform, and wheel/source mode.
- wall time and peak RSS.
- whether broad Python-side caches were materialized.
- what counts were compared: files, symbols, imports, exports, references, dependencies, parse errors, and codemod touched files.

## Vercel Path

Recommended Vercel project:

```text
Framework Preset: Next.js
Root Directory: site
Build Command: default
Output Directory: default
Install Command: default
Node.js: 22.x
Runtime Env Vars: none required today
Production Branch: integrator-approved trunk branch
```

No checked-in `vercel.json` is required for the current app if Vercel project settings define `site` as the root directory. Add `site/vercel.json` only if the project needs repo-portable settings such as redirects, headers, or pinned framework behavior.

Read-only/project setup checks:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
vercel whoami
vercel --version
vercel link --cwd site
vercel pull --cwd site --environment=preview --yes
```

Preview deploy flow after approval:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npm --prefix site ci
npm --prefix site run build
vercel deploy --cwd site --yes
```

Prebuilt preview alternative:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
vercel pull --cwd site --environment=preview --yes
vercel build --cwd site
vercel deploy --cwd site --prebuilt --yes
```

Production cutover requires explicit approval:

- attach `graph-sitter.com` to the Vercel landing project
- attach or redirect `www.graph-sitter.com`
- keep `docs.graph-sitter.com` pointed at docs hosting
- update `hatch.toml` documentation URL if final docs URL differs from current metadata

Do not run `vercel deploy --prod`, promote a deployment, or attach domains from a subagent task.

## Codex Skill Packaging

Keep the skill as a small operating guide, not a copy of the docs.

Recommended source artifact:

```text
rust-rewrite/skill-prototype/graph-sitter/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── cli.md
    ├── codemods.md
    └── rust-backend.md
```

The skill should document:

- when to use Graph-sitter versus ordinary file inspection
- local checkout commands through `uv run`
- released package commands through `uvx graph-sitter ...`
- branch wheel commands through `uvx --from dist/<wheel>.whl`
- strict Rust mode and fallback semantics
- large-repo scoping through `--subdir`
- transform safety: `--check`, inspect diff, then `--write`
- correctness caveat: parity is not the same as absolute semantic correctness

Release gates before distributing the skill:

- published docs contain the same setup commands the skill recommends
- `uvx graph-sitter doctor`, `parse`, `run`, and `transform` work from a clean installed package
- the skill validator passes on the final skill folder
- one fresh-agent read-only parse task succeeds
- one fresh-agent checked codemod task succeeds before write mode is attempted
- benchmark and correctness claims link to current docs or committed reports

## Multi-Agent Work Convention

Use this file as the work ledger for docs, landing, Vercel, and skill tasks.

Rules:

- Agents claim one unchecked item by editing the line to include `owner: <agent-name>`.
- Agents mark `[x]` only after the artifact is changed and validated.
- Each completed item should include a terse `Result:` note with the changed file or validation command.
- Agents must not edit implementation code from this workstream unless the integrator explicitly expands scope.
- Deployment tasks require explicit integrator approval before any production action.

## Task Checklist

### Docs Architecture

- [x] Create docs/site strategy. owner: docs-vercel-subagent. Result: `rust-rewrite/docs-site-strategy.md`.
- [ ] Decide whether docs stay on Mintlify for launch or migrate to Vercel MDX. owner: unclaimed.
- [ ] Add a docs release gate checklist to `rust-rewrite/strategy.md` or keep this file as the docs ledger. owner: unclaimed.
- [x] Audit `docs/introduction/installation.mdx` against current `uv run`, `uv tool install`, and `uvx` behavior. owner: codex. Result: installation docs now distinguish installed tool, local source, published-package `uvx`, and branch-built wheel validation.
- [x] Add or update a dedicated `docs/cli/uvx.mdx` page with release-gated package guidance. owner: codex. Result: added `docs/cli/uvx.mdx` for parse, run, transform, backend, safety, `--subdir`, and release-gate workflows.
- [ ] Add Rust backend architecture/status docs sourced from `rust-rewrite/supported-subset.json` and current wheel checks. owner: unclaimed.
- [x] Add correctness/parity docs that distinguish old-backend parity from semantic correctness. owner: codex. Result: added `docs/correctness/parity.mdx` with supported-scope evidence, known deltas, safety modes, and pre-default gates.
- [x] Add large-repo benchmark docs for pinned Airflow and pinned Next.js after fresh measurements. owner: codex. Result: added `docs/benchmarks/large-repos.mdx` with Codebase, installed-wheel, and codemod proof summaries.

### Landing Page

- [ ] Review `site/app/page.tsx` copy for release-gated claims before the first public preview. owner: unclaimed.
- [ ] Add a landing-page CTA to the exact docs quickstart once the docs URL is final. owner: unclaimed.
- [ ] Verify `site` builds from a clean install with Node 22. owner: unclaimed.
- [ ] Add landing-page screenshots or visual QA notes before production domain cutover. owner: unclaimed.

### Vercel

- [ ] Link or create the Vercel project with root directory `site`. owner: unclaimed.
- [ ] Pull preview env with `vercel pull --cwd site --environment=preview --yes`. owner: unclaimed.
- [ ] Run a preview deploy for review only. owner: unclaimed.
- [ ] Record the preview URL in this file or the integrator thread. owner: unclaimed.
- [ ] Confirm `docs.graph-sitter.com` hosting before apex cutover. owner: unclaimed.
- [ ] Attach `graph-sitter.com` and `www.graph-sitter.com` only after explicit approval. owner: blocked-pending-approval.

### Skill

- [ ] Finalize `rust-rewrite/skill-prototype/graph-sitter/SKILL.md` after CLI/docs commands stabilize. owner: unclaimed.
- [ ] Validate the skill with the Codex skill validator. owner: unclaimed.
- [ ] Forward-test the skill with a fresh-agent read-only parse task. owner: unclaimed.
- [ ] Forward-test the skill with a fresh-agent codemod task using `--check` before `--write`. owner: unclaimed.
- [ ] Document skill installation/distribution in public docs once release gates pass. owner: unclaimed.

### JS/TS Documentation

- [ ] Add a tested TypeScript parse quickstart using pinned Next.js or a small TS fixture. owner: unclaimed.
- [ ] Add a TypeScript transform/codemod example with `--check` and `--write`. owner: unclaimed.
- [ ] Document current JS/React support boundaries using tested behavior. owner: unclaimed.
- [ ] Keep TS examples aligned with `rust-rewrite/tools/check_wheel_pinned_typescript_repo.py`. owner: unclaimed.

### Release Readiness

- [ ] Ensure PyPI package metadata points to the final docs and landing URLs. owner: unclaimed.
- [ ] Ensure the public setup path does not claim `uvx graph-sitter ...` until clean package validation passes. owner: unclaimed.
- [x] Add a docs validation CI or release gate for `mintlify validate`. owner: codex. Result: `.github/workflows/docs-validate.yml` runs Mintlify validate and broken-link checks for docs changes.
- [ ] Add a site build CI or release gate for `npm --prefix site ci && npm --prefix site run build`. owner: unclaimed.
