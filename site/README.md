# Graph-sitter Site

Next.js landing page scaffold for the Vercel project that will own the
`graph-sitter.com` apex after review. The product docs remain a separate
Mintlify project in `../docs`.

The landing page is intentionally small: it explains the product, points to the
docs, and sets expectations for the Rust rewrite and future
`uvx graph-sitter ...` command surface. It should not try to render or replace
the Mintlify docs tree.

## Prerequisites

- Node.js 22 or newer.
- npm, using the checked-in `package-lock.json`.
- Vercel CLI for preview deploys: `npm i -g vercel`, or an existing global
  `vercel` binary.

If the active Node install fails locally, prefer a Node 22 runtime from `nvm`
or another version manager before running build or Vercel commands:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
```

## Local Development

```bash
cd site
npm ci
npm run dev
```

Open the printed localhost URL.

## Build Check

```bash
cd site
npm run build
```

For a Vercel-shaped local build without deploying:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npx vercel pull --cwd site --environment=preview --yes
npx vercel build --cwd site
```

## Vercel Preview Deploy

The lowest-risk setup is a dedicated Vercel project whose root directory is
`site`.

Recommended project settings:

```text
Framework Preset: Next.js
Root Directory: site
Build Command: default
Output Directory: default
Install Command: default
Production Branch: the integrator-approved trunk branch
```

From an authenticated Vercel CLI session:

```bash
export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"
npx vercel whoami
npx vercel link --cwd site
npx vercel pull --cwd site --environment=preview --yes
npx vercel deploy --cwd site --yes
```

This creates a preview deployment. Do not pass `--prod`, attach
`graph-sitter.com`, or attach `www.graph-sitter.com` until the integrator
approves the docs-domain cutover.

If the Vercel project is already linked and you are running from the repository
root, this equivalent command keeps the deployment scoped to the landing app:

```bash
npx vercel pull --cwd site --environment=preview --yes
npx vercel deploy --cwd site --yes
```

For a prebuilt preview deployment:

```bash
npx vercel pull --cwd site --environment=preview --yes
npx vercel build --cwd site
npx vercel deploy --cwd site --prebuilt --yes
```

Vercel should use Node.js 22.x. No runtime environment variables are required
for the current static landing page.

## Production Cutover Sequence

1. Keep the current docs production site untouched.
2. Review a Vercel preview deployment for `site/`.
3. Move or confirm docs at `docs.graph-sitter.com`.
4. Attach `graph-sitter.com` and `www.graph-sitter.com` to the Vercel landing
   project only after explicit approval.
