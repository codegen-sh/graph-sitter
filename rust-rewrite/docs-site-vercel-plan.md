# Vercel Docs Site Plan

Last updated: 2026-06-20

Use the custom Next.js app in `site/` for both the product landing page and
documentation. The app renders the repository's `docs/` content directly and is
the only docs hosting path represented in this branch.

## Vercel Project

Recommended project settings:

```text
Framework Preset: Next.js
Root Directory: site
Build Command: default
Output Directory: default
Install Command: default
Node.js Version: 22.x
Production Branch: integrator-approved trunk branch
```

No runtime environment variables are required for the current static landing and
docs app.

## Preview Flow

From an authenticated Vercel CLI session:

```bash
npx vercel whoami
npx vercel link --cwd site
npx vercel pull --cwd site --environment=preview --yes
npm --prefix site ci
npm --prefix site run build
npx vercel deploy --cwd site --yes
```

For a prebuilt preview:

```bash
npx vercel pull --cwd site --environment=preview --yes
npx vercel build --cwd site
npx vercel deploy --cwd site --prebuilt --yes
```

Do not pass `--prod` or attach production domains without explicit user approval.

## CI

`.github/workflows/site-build.yml` is the repository gate for the custom docs
site. It runs for:

- `.github/workflows/site-build.yml`
- `site/**`
- `docs/**`

The gate installs from `site/package-lock.json` and runs the production Next.js
build.

## Launch Checklist

- [ ] Confirm the Vercel project points at `site/`.
- [ ] Confirm `/`, `/docs`, `/docs/cli/uvx`, `/docs/benchmarks/large-repos`,
  `/docs/correctness/parity`, and representative API pages render in a
  preview deployment.
- [ ] Confirm docs search JSON builds at `/docs/search.json`.
- [ ] Add redirects for any old public docs URLs before domain cutover.
- [ ] Attach production domains only after explicit approval.
- [ ] Validate a released package path before public docs claim
  `uvx graph-sitter ...` works from PyPI.

## Notes For Future Agents

- Keep docs content in `docs/` until there is a deliberate content migration.
- Keep app-specific UI, search, navigation, and deployment code in `site/`.
- If adding generated docs, make sure they build under the Next app without
  external-host-specific MDX components.
- If changing `docs/**`, run the Next site build because docs content is part of
  the app bundle.
