# Docs Site and Vercel Plan

## Decision

Keep the public landing page and product documentation as two separate
surfaces.

- `docs/` remains the Mintlify documentation source of truth.
- `site/` remains a small Next.js landing page for Vercel.
- `graph-sitter.com` should eventually point at the Vercel landing project.
- `www.graph-sitter.com` should redirect or alias to the Vercel landing project.
- `docs.graph-sitter.com` should point at the Mintlify docs project.

This keeps the generated API reference, Mintlify MDX components, CLI docs, and
codemod tutorials out of the marketing app. The landing page should send people
to the docs instead of attempting to render the docs tree itself.

## Recommended Stack

Use the stack that already exists in this repo:

- Mintlify in `docs/` for product documentation, tutorials, generated API
  reference pages, and release-gated setup instructions.
- Next.js in `site/` for a small Vercel-hosted landing page.
- Vercel only for the landing project, with project root set to `site`.

This split is the lowest-risk path because the repo already has Mintlify source
content, generated docs workflow wiring, a separate Next.js landing app, and
app-local ignore rules for Vercel/build artifacts. It also keeps docs releases
from being coupled to landing-page deploys.

## Current Findings

- [x] `docs/` is a Mintlify project configured by `docs/mint.json`.
- [x] `docs/**/*.mdx` contains the human-authored docs, examples, tutorials,
  CLI pages, and API reference pages.
- [x] `.github/workflows/generate-docs.yml` regenerates API reference docs and
  the system prompt on pushes to `develop`.
- [x] `site/` is a conventional Next.js app with `npm run dev`, `npm run build`,
  and a checked-in `site/package-lock.json`.
- [x] `site/app/page.tsx` already states the product direction: Python as the
  authoring shell, Rust for the large graph/index backend, and
  `uvx graph-sitter ...` as the future command surface.
- [x] `site/.gitignore` ignores `.next`, `node_modules`, `out`, `.vercel`,
  TypeScript build info, and local env files.
- [x] No repo-level `vercel.json`, `site/vercel.json`, `.vercel/`, or
  `.openai/hosting.json` is checked in.
- [x] A working Vercel CLI was verified locally through Node 22:
  `PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH" npx vercel --version`
  returns `Vercel CLI 54.7.1`.
- [x] Authenticated Vercel user was verified with `vercel whoami`:
  `jayhack`.
- [ ] Vercel project link state, project ownership, and team scope still need
  to be verified before any preview deploy.
- [ ] Mintlify project ownership and custom-domain state still need to be
  verified outside this repo.

## Mintlify Docs vs Vercel Landing Site

Mintlify owns durable product documentation:

- setup and installation
- `uvx graph-sitter ...` once the command is released
- Python API usage
- codemod authoring and execution
- backend/fallback semantics
- supported languages and known limits
- generated API reference
- tutorials, migration guides, and troubleshooting

Vercel owns the simple landing page:

- one-sentence explanation of Graph-sitter
- why a graph-aware codemod library matters
- Python shell plus Rust backend positioning
- compact examples for parsing and transforming
- conservative `uvx graph-sitter ...` preview copy
- links to docs and GitHub

The landing page should not include exhaustive setup steps, API reference
tables, generated docs, or detailed Rust parity claims. Those belong in
Mintlify and should only ship after the release gates below pass.

## Proposed Information Architecture

Recommended URLs after launch:

```text
https://graph-sitter.com                       -> Vercel project rooted at site/
https://www.graph-sitter.com                   -> Vercel alias or redirect
https://docs.graph-sitter.com                  -> Mintlify project rooted at docs/
https://docs.graph-sitter.com/api-reference    -> Mintlify generated API pages
```

Recommended landing-page shape in `site/`:

- `/`: simple product page explaining that Graph-sitter builds codebase graphs
  for repository queries and codemods.
- Hero: name and literal offer, not benchmark claims.
- Quick example: `Codebase("./")` Python shell usage.
- Capabilities: parse, graph, transform.
- Architecture: Python shell, compact Rust backend, explicit fallback status.
- CLI preview: `uvx graph-sitter parse ...` and `uvx graph-sitter transform ...`
  only with release-gated wording.
- CTAs: docs and GitHub.

Recommended Mintlify docs shape:

- `introduction/overview`: short definition, supported languages, and status.
- `introduction/installation`: current stable install path and Python versions.
- `introduction/getting-started`: quickstart with one parse/query/edit
  walkthrough.
- `cli/uvx`: target `uvx graph-sitter ...` commands for parse, run, and
  transform after published-package validation passes.
- `cli/*`: existing `gs` workspace commands and compatibility notes.
- `codemods/overview`: transformation model, check/write modes, and rollback
  expectations.
- `codemods/examples`: focused Python and TypeScript codemod examples that
  match tested behavior.
- `architecture/python-shell-rust-core`: how the Rust engine, Python handles,
  strict mode, and fallback mode fit together.
- `architecture/supported-subset`: current supported Rust-backed APIs and open
  gaps sourced from `rust-rewrite/supported-subset.json`.
- `benchmarks/large-repos`: pinned Airflow and Next.js benchmark methodology,
  latency, and RSS numbers only after artifact-level reports are current.
- `correctness/parity`: how golden graph snapshots, semantic parity checks,
  and codemod proofs are validated.
- `skill/graph-sitter`: Codex skill install/use page once the skill path is
  finalized and tested.
- `building-with-graph-sitter/*`: durable API and concept guides that remain
  accurate for the Python shell.
- `api-reference/*`: generated pages only, refreshed by the docs workflow.

## Vercel Project and Deploy Flow

Use a dedicated Vercel project with these settings:

```text
Framework Preset: Next.js
Root Directory: site
Build Command: default
Output Directory: default
Install Command: default
Node.js: 22.x
Production Branch: integrator-approved trunk branch
Runtime Environment Variables: none required today
```

Preview-only flow from the repository root:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npx vercel whoami
npx vercel link --cwd site
npx vercel pull --cwd site --environment=preview --yes
npx vercel deploy --cwd site --yes
```

If the project is already linked:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npx vercel pull --cwd site --environment=preview --yes
npx vercel deploy --cwd site --yes
```

Optional prebuilt preview flow:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npx vercel pull --cwd site --environment=preview --yes
npx vercel build --cwd site
npx vercel deploy --cwd site --prebuilt --yes
```

Do not run `npx vercel deploy --cwd site --prod`, promote a deployment, or
attach `graph-sitter.com` / `www.graph-sitter.com` until the integrator
explicitly approves production cutover.

## Vercel Files, Env, And Secret Hygiene

- Keep `.vercel/` untracked. `site/.gitignore` already covers `site/.vercel`;
  if a root-level Vercel command creates `./.vercel`, remove it or add a
  root-level ignore before committing anything.
- Do not commit `.env.local`, `.env.*.local`, Vercel tokens, team IDs from
  shell history, or downloaded runtime env values.
- Prefer `vercel link --cwd site` and `vercel pull --cwd site ...` so generated
  project metadata stays under the ignored `site/.vercel/` directory.
- If runtime env vars are needed later, manage them in the Vercel dashboard or
  through `vercel env` and document only the variable names and purposes in the
  repo.
- The current landing page should need no runtime env vars.
- A committed `site/vercel.json` is unnecessary today. Add one only if routing,
  headers, redirects, or enforced framework/build settings cannot be expressed
  through Vercel project settings.

## Local Verification Commands

If the active Node install fails locally, prefer a Node 22 runtime from `nvm`
or another version manager before running landing-page or Vercel commands:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
```

Landing page:

```bash
cd site
npm ci
npm run build
```

Vercel build check without deploying:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npx vercel pull --cwd site --environment=preview --yes
npx vercel build --cwd site
```

Docs:

```bash
cd docs
npx --yes mintlify@latest validate
npx --yes mintlify@latest broken-links
```

Mintlify may warn that `mint.json` is legacy config and may generate
`docs.json`. Treat `docs/mint.json` as the checked-in source of truth until a
docs owner explicitly approves a config migration.

## Release Gate Checklist

- [ ] Confirm canonical domain split: apex/www on Vercel, `docs.` on Mintlify.
- [ ] Verify Vercel account/team with `npx vercel whoami`.
- [ ] Confirm or create a Vercel project whose root directory is exactly
  `site`.
- [ ] Produce a Vercel preview deployment for review without `--prod`.
- [ ] Review landing page at desktop and mobile widths.
- [ ] Validate Mintlify docs navigation and broken links.
- [ ] Update stale docs copy that still says Codegen where it should say
  Graph-sitter, without erasing legitimate company attribution.
- [ ] Update install/setup docs once the release command is final.
- [ ] Document both `gs` compatibility commands and the new
  `uvx graph-sitter ...` commands.
- [ ] Confirm artifact-level wheel smoke tests pass for parse and transform
  before advertising `uvx graph-sitter` as the public path.
- [ ] Confirm Rust-backed parse/transform support and fallback semantics before
  making Rust the default backend in docs.
- [ ] Confirm the Codex skill installation path and link from docs only after
  the skill package is ready.
- [ ] Move or confirm docs at `docs.graph-sitter.com`.
- [ ] Attach `graph-sitter.com` and `www.graph-sitter.com` to Vercel only after
  explicit production approval.

## Concrete Next Tasks

- [ ] Link the existing authenticated Vercel account to a dedicated landing
  project with `vercel link --cwd site`; confirm root directory is `site`.
- [ ] Run `npx vercel pull --cwd site --environment=preview --yes` and confirm
  only ignored `site/.vercel/` metadata is created.
- [ ] Run `npm ci && npm run build` inside `site/` and fix any landing build
  errors before preview deployment.
- [ ] Create a Vercel preview deployment with
  `npx vercel deploy --cwd site --yes`; record the preview URL in the PR or
  integration thread, not in permanent docs.
- [ ] Review the landing page at desktop and mobile widths; keep copy
  conservative around Rust performance, correctness, and `uvx` until release
  gates pass.
- [ ] Add or update Mintlify docs pages for quickstart, `uvx` CLI,
  transformations/codemods, Rust architecture, benchmark methodology,
  correctness/parity, and skill distribution.
- [ ] Make docs examples use commands that are backed by current tests:
  `graph-sitter parse`, `graph-sitter transform --check|--write`, strict
  backend flags, and fallback behavior.
- [ ] Generate or refresh API docs through the existing docs workflow instead
  of hand-editing generated `api-reference` pages.
- [ ] Validate docs with `npx --yes mintlify@latest validate` and
  `npx --yes mintlify@latest broken-links`; triage legacy Mintlify config
  warnings separately from content errors.
- [ ] Decide whether to keep `docs/mint.json` or migrate to Mintlify's newer
  `docs.json` format; do not migrate opportunistically during landing work.
- [ ] Wire final `uvx graph-sitter ...` setup instructions to the published
  wheel release once `uvx-command-roadmap.md` gates pass.
- [ ] Publish the Codex skill only after the reviewed skill folder, CLI
  commands, and setup docs all agree.

## Known Risks and Open Decisions

- The docs still contain legacy `Codegen` wording, `gs`-first CLI examples, and
  some source links to `develop`. These need a targeted docs pass, not a broad
  blind replacement.
- Current docs say Graph-sitter guarantees transformation correctness. Product
  direction is more careful: we should document tested behavior, parity scope,
  and known limits instead of claiming universal correctness.
- The final default backend is still a release decision. Until published wheels
  and large-repo parity gates pass, public docs should prefer explicit backend
  examples and clear fallback semantics.
- The landing page can mention the Rust rewrite and `uvx graph-sitter`, but it
  should avoid promising performance numbers until benchmark methodology and
  artifact-level tests are published.
- The Vercel project is not linked in the repo yet. Any `.vercel/` directory
  created during manual linking should stay untracked unless the team decides
  to commit project metadata.
- Mintlify custom-domain settings are not represented in this repo, so the docs
  domain cutover requires account-level verification.
- The repository already has `site/.next` and `site/node_modules` locally, but
  they are ignored by `site/.gitignore`; do not treat local build artifacts as
  source.
