# Docs Site, Landing Page, and Vercel Plan

## Current repo state

- The existing docs live in `docs/` and are configured by `docs/mint.json`.
- `docs/mint.json` uses the legacy Mintlify schema and points public metadata at `https://graph-sitter.com`.
- The docs navigation includes the `introduction/*`, `tutorials/*`, `building-with-graph-sitter/*`, `cli/*`, `blog/*`, `changelog/*`, and generated `api-reference/*` source trees.
- A small Next.js landing app now exists in `site/`.
- The root `package.json` is only semantic-release metadata; it does not define a website build.
- The Python package metadata in `pyproject.toml` identifies `graph-sitter` as a Python library for codebase analysis and transformation.
- The Rust rewrite branch now has a Cargo workspace for `crates/graph-sitter-engine` and `crates/graph-sitter-py`, but no website-specific Rust build surface.
- `.github/workflows/generate-docs.yml` regenerates API reference MDX under `docs/` on pushes to `develop` by running `uv run python src/graph_sitter/gscli/cli.py generate docs`.
- The current local Homebrew `node` binary is broken on this machine because it cannot load `libllhttp.9.3.dylib`; the working runtime used for checks is `~/.nvm/versions/node/v22.19.0/bin`.

## Recommended architecture

Keep docs and landing separate.

1. **Docs:** keep Mintlify as the docs renderer for `docs/`.
   - This preserves the current `mint.json` navigation, MDX components, generated API reference pages, blog/changelog content, and docs generation workflow.
   - Connect Mintlify to the repo for production deploys and PR previews.
   - Move docs to `docs.graph-sitter.com` when the landing page is ready, or keep `graph-sitter.com` on Mintlify until the landing page cutover.

2. **Landing page:** add a small Vercel-owned web app in a disjoint path, preferably `site/`.
   - Use a conventional Vercel framework such as Next.js.
   - Configure the Vercel project Root Directory to `site`.
   - Let Vercel manage PR preview deployments.
   - Point `graph-sitter.com` and `www.graph-sitter.com` to this Vercel project only after the integrator approves cutover.

3. **Cross-linking:**
   - Landing page primary CTA: docs at `https://docs.graph-sitter.com/introduction/getting-started`.
   - Landing page secondary CTA: GitHub at `https://github.com/codegen-sh/graph-sitter`.
   - Docs topbar CTA can remain GitHub, but docs should add a top-level link back to the landing page after domain cutover.

This avoids trying to make Mintlify run inside Vercel. The current `docs/` tree is a Mintlify project source, not a checked-in static output directory or a package with a Vercel build command.

## Vercel path

The first landing scaffold now lives under:

```text
site/
  package.json
  package-lock.json
  next.config.mjs
  tsconfig.json
  app/
    page.tsx
    layout.tsx
    globals.css
  README.md
```

It is a small Next.js app with local instructions in `site/README.md`. It keeps
Vercel configuration in project settings rather than adding root-level routing
or build metadata.

Recommended Vercel project settings:

```text
Project name: graph-sitter-site
Root Directory: site
Framework Preset: Next.js
Build Command: default
Output Directory: default
Install Command: default
Production Branch: develop, or the eventual trunk branch chosen by the integrator
```

Do not add a root-level `vercel.json` unless the repo later has multiple Vercel projects that need explicit routing or build overrides. Keeping project settings in Vercel avoids surprising the Python/Rust package workflows.

## Landing page message

The landing page should explain Graph-sitter plainly:

> Graph-sitter lets you write Python programs that understand and safely edit whole codebases. It parses Python, TypeScript, JavaScript, and React code, builds a graph of files, symbols, imports, calls, and usages, then gives you high-level APIs for refactors, analysis, codemods, and codebase automation without hand-editing syntax trees.

Implemented first-screen structure:

- Eyebrow: `Codebase graphs for codemods`
- H1: `A codebase graph and codemod library.`
- One-sentence body: says Graph-sitter lets Python programs parse repositories into files, symbols, imports, calls, and usages, then query those relationships and make targeted edits.
- Primary CTA: `Read the docs`
- Secondary CTA: `View on GitHub`
- Code sample: a short `Codebase("./")` example that removes unused functions or moves symbols while updating imports.

Avoid over-positioning it as a generic AI tool. The clearest differentiator is programmatic codebase manipulation: parse once, query relationships, perform safe edits, commit changes.

## Docs cleanup before cutover

- Keep `docs/mint.json` branding on Graph-sitter rather than legacy Codegen product metadata.
- Decide whether generated API reference pages should continue to link to `develop` source URLs while `rust-rewrite` is active. Today generated pages commonly link to `github.com/codegen-sh/graph-sitter/blob/develop/...`.
- Keep the docs generator workflow scoped to `develop` unless the Rust rewrite branch needs a separate preview workflow.
- Validate the docs tree with `npx --yes mintlify@latest validate` and `npx --yes mintlify@latest broken-links` after any navigation or slug change. The latest CLI may generate a local `docs.json` migration artifact from `mint.json`; do not commit that migration unless the docs owner approves switching config formats.

## Local and preview commands

Use the nvm Node runtime on this machine until Homebrew Node is repaired:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
```

Landing page:

```bash
cd site
npm ci
npm run build
vercel whoami
vercel deploy --yes
```

Docs:

```bash
cd docs
npx --yes mintlify@latest dev --port 3333
npx --yes mintlify@latest validate
npx --yes mintlify@latest broken-links
```

`vercel deploy --yes` from `site/` creates a preview deployment when the CLI is authenticated and linked. Do not pass `--prod`, promote aliases, or attach the apex/www domains without explicit integrator approval.

## Deployment sequencing

1. Keep current docs production untouched.
2. Add `site/` app on a feature branch.
3. Create a Vercel project with Root Directory `site`.
4. Use Vercel PR preview URLs for review. Do not attach production domains yet.
5. Configure Mintlify docs preview/deploy for `docs/` if it is not already connected.
6. After review, move docs to `docs.graph-sitter.com`.
7. Attach `graph-sitter.com` and `www.graph-sitter.com` to the Vercel landing project.
8. Update README/docs links if the docs canonical URL changes.

## Blockers and open questions

- Need confirmation of the desired canonical docs URL: keep `graph-sitter.com` as docs, or move docs to `docs.graph-sitter.com` and use the apex for landing.
- Need to verify current Mintlify project ownership/custom-domain settings outside the repo.
- Need Vercel project link/ownership for preview deploys from `site/`.
- Need Homebrew Node repaired or the documented nvm runtime used for local checks.
- No production Vercel deployment should happen until the integrator decides timing.
