# Graph-sitter Docs

The checked-in docs are a Mintlify project. Keep them separate from the Vercel
landing app in `../site`; the repo does not currently contain a Vercel-buildable
static export of these docs.

## Local Development

From this directory:

```bash
npx --yes mintlify@latest dev --port 3333
```

Open the printed localhost URL. The `MDX` editor extension is useful when
editing these pages.

## Validation

```bash
npx --yes mintlify@latest validate
npx --yes mintlify@latest broken-links
```

Run these before moving navigation entries or changing page slugs.

The current CLI may print a legacy-config warning and generate `docs.json` from
`mint.json`. Treat `mint.json` as the checked-in source of truth until a docs
config migration is explicitly approved.

## Adding New Pages

- Edit the page as a `.mdx` doc.
- Add the page path to `mint.json` so it appears in the navigation.
- Keep generated API reference pages under `api-reference/` in sync with the
  docs generation workflow.

## Hosting

Mintlify should continue to host the docs tree. The recommended launch sequence
is to keep the current docs production domain untouched, review the Vercel
landing preview from `../site`, then move or confirm docs at
`docs.graph-sitter.com` before the apex domain moves to Vercel.
