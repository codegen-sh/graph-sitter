# Docs Site, Landing Page, and Vercel Plan

## Current repo state

- The existing docs live in `docs/` and are configured by `docs/mint.json`.
- `docs/mint.json` uses the Mintlify schema and points public metadata at `https://graph-sitter.com`.
- There is no existing Next.js, Vite, Astro, Docusaurus, or static website app in the repo.
- The root `package.json` is only semantic-release metadata; it does not define a website build.
- The Python package metadata in `pyproject.toml` identifies `graph-sitter` as a Python library for codebase analysis and transformation.
- The Rust rewrite branch now has a Cargo workspace for `crates/graph-sitter-engine` and `crates/graph-sitter-py`, but no website-specific Rust build surface.
- `.github/workflows/generate-docs.yml` regenerates API reference MDX under `docs/` on pushes to `develop` by running `uv run python src/graph_sitter/gscli/cli.py generate docs`.
- A quick `docs/mint.json` navigation check found one missing page reference: `cli/expert` is listed but `docs/cli/expert.mdx` is not present.

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

Recommended first-screen structure:

- H1: `Graph-sitter`
- Subhead: `Write code that understands and edits codebases.`
- One-sentence body: use the plain-language paragraph above, shortened for readability.
- Primary CTA: `Read the docs`
- Secondary CTA: `View on GitHub`
- Code sample: a short `Codebase("./")` example that removes unused functions or moves symbols while updating imports.

Avoid over-positioning it as a generic AI tool. The clearest differentiator is programmatic codebase manipulation: parse once, query relationships, perform safe edits, commit changes.

## Docs cleanup before cutover

- Fix or remove the missing `cli/expert` nav entry.
- Decide whether generated API reference pages should continue to link to `develop` source URLs while `rust-rewrite` is active. Today generated pages commonly link to `github.com/codegen-sh/graph-sitter/blob/develop/...`.
- Keep the docs generator workflow scoped to `develop` unless the Rust rewrite branch needs a separate preview workflow.
- Audit `docs/mint.json` branding before domain cutover. It currently says `Codegen` for site name and Open Graph title while the public domain is `graph-sitter.com`.

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
- Need confirmation of the landing app stack. Next.js on Vercel is the simplest path, but it introduces a real frontend package where none exists today.
- Need to resolve the missing `docs/cli/expert.mdx` page before relying on docs preview health.
- Need to verify current Mintlify project ownership/custom-domain settings outside the repo.
- No Vercel deployment should happen until the integrator decides timing.
