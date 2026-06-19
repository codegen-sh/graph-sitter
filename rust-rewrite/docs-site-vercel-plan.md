# Docs Site and Vercel Plan

## Decision

Keep the documentation renderer and marketing surface separate.

- `docs/` remains the Mintlify documentation source.
- `site/` is the small Next.js landing page intended for Vercel.
- `graph-sitter.com` should eventually point at the Vercel landing page.
- `docs.graph-sitter.com` should point at Mintlify docs after domain cutover.

This avoids forcing the Mintlify MDX tree into Vercel and keeps package,
workflow, and generated API-reference concerns out of the landing app.

## Current Findings

- [x] `site/` already contains a conventional Next.js app with `npm run build`.
- [x] `site/README.md` documents local development and preview deploy commands.
- [x] No `.openai/hosting.json` exists, so OpenAI Sites hosting is not configured for this repo.
- [x] `docs/` is a Mintlify project configured by `docs/mint.json`.
- [x] The current landing copy now explains parsing codebases, graphing imports/references/calls/usages, codemods, Python as the shell, Rust as the scale backend, and the future `uvx graph-sitter` command surface.
- [ ] Vercel project ownership/link state still needs to be verified with the authenticated CLI.
- [ ] Mintlify project ownership/custom-domain state still needs to be verified outside the repo.

## Docs Architecture

Recommended URLs after launch:

```text
https://graph-sitter.com                       -> Vercel project rooted at site/
https://www.graph-sitter.com                   -> Vercel alias/redirect
https://docs.graph-sitter.com                  -> Mintlify project rooted at docs/
https://docs.graph-sitter.com/api-reference    -> Generated API reference pages
```

The landing page should keep only product-level content:

- What Graph-sitter does: parse repositories into symbols and relationships.
- Why it exists: codebase-aware analysis and transformations.
- How it is used today: Python API and codemod scripts.
- Where it is going: Rust-backed graph indexes and `uvx graph-sitter ...`.
- Where to go next: docs and GitHub.

The Mintlify docs should own setup, API reference, tutorials, CLI reference,
and codemod walkthroughs.

## Vercel Setup

Use a dedicated Vercel project with these settings:

```text
Framework Preset: Next.js
Root Directory: site
Build Command: default
Output Directory: default
Install Command: default
Node.js: 22.x
Production Branch: integrator-approved trunk branch
```

Preview deploy from an authenticated CLI:

```bash
vercel whoami
vercel link --cwd site
vercel deploy --cwd site --yes
```

If already linked:

```bash
vercel deploy --cwd site --yes
```

Do not run `vercel deploy --prod`, attach `graph-sitter.com`, or attach
`www.graph-sitter.com` until the integrator explicitly approves production
cutover.

## Local Verification

Use the working Node runtime on this machine if Homebrew Node is broken:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
```

Landing page:

```bash
cd site
npm ci
npm run build
```

Docs:

```bash
cd docs
npx --yes mintlify@latest validate
npx --yes mintlify@latest broken-links
```

The docs commands may propose a Mintlify config migration from `mint.json`.
Do not commit generated migration files unless the docs owner approves the
format change.

## Production Launch Checklist

- [ ] Confirm final canonical domains: apex for landing, `docs.` for Mintlify.
- [ ] Verify Vercel project ownership and link state with `vercel whoami`.
- [ ] Create or confirm the Vercel project root is `site/`.
- [ ] Generate a Vercel preview deployment and review desktop/mobile pages.
- [ ] Validate Mintlify docs navigation and broken links.
- [ ] Update stale docs references that still say Codegen where they should say Graph-sitter.
- [ ] Update setup docs once the release command is final: stable Python install now, `uvx graph-sitter ...` when published.
- [ ] Confirm PyPI/wheel status for Rust-backed parsing before advertising Rust as the default install path.
- [ ] Move docs to `docs.graph-sitter.com`.
- [ ] Attach `graph-sitter.com` and `www.graph-sitter.com` to Vercel only after explicit approval.

## Known Content Gaps

- `docs/graph-sitter/getting-started.mdx` still mixes legacy wording and the current CLI path.
- `docs/cli/*` is still centered on `gs ...`; it should eventually describe the stable CLI and the new `uvx graph-sitter` path separately.
- Generated API pages may still link to `develop` source URLs while `rust-rewrite` is active.
- The landing page should stay conservative until Rust-backed wheels and parity tests are release-ready.
