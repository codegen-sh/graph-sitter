# Docs Site Strategy

Last updated: 2026-06-20

The docs and landing page now live in the custom Next.js app under `site/`.
The app renders MD/MDX content from `docs/` at `/docs`, and the Vercel project
should use `site` as its root directory.

## Architecture

- `site/`: Next.js application for the landing page, docs routes, search JSON,
  and Vercel deployment.
- `docs/`: source MD/MDX content rendered by `site/app/docs/[[...slug]]/page.tsx`.
- `site/lib/docs.ts`: docs router, content loader, generated navigation,
  search index, link rewriting, heading extraction, and MDX preprocessing.
- `.github/workflows/site-build.yml`: CI gate for both `site/**` and `docs/**`
  changes via `npm --prefix site ci && npm --prefix site run build`.

## Current Decisions

- The custom Next.js app is the target docs solution.
- The old external docs renderer has been retired from repo configuration.
- Docs navigation is derived from the checked-in content tree, not from a vendor
  config file.
- Domain cutover remains a user/integrator decision; do not deploy production
  or attach domains without explicit approval.
- Public copy must stay conservative about the Rust rewrite: say "strict Rust
  mode" or "supported subset" until published packages and parity gates prove
  broader claims.

## Validation

Run from the repository root:

```bash
npm --prefix site ci
npm --prefix site run build
```

For Vercel-shaped preview validation:

```bash
npx vercel pull --cwd site --environment=preview --yes
npx vercel build --cwd site
npx vercel deploy --cwd site --prebuilt --yes
```

## Open Work

- [ ] Add redirects for any old public docs slugs before domain cutover. owner:
      docs/site agent. Notes: verify from access logs or the previous host's URL
      map if available.
- [ ] Add a TypeScript transform/codemod docs example with `--check` and
      `--write`. owner: docs/site agent.
- [ ] Forward-test the repository-local skill with a fresh-agent codemod task
      using `--check` before `--write`. owner: skill/docs agent.
- [ ] Add published-package `uvx graph-sitter` validation transcript after a
      real release artifact exists. owner: release/docs agent.
- [ ] Add docs search quality checks once the content tree stabilizes. owner:
      docs/site agent.
