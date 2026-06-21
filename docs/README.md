# Graph-sitter Docs

The checked-in docs are MD/MDX content rendered by the custom Next.js app in
`../site`. The docs are available under `/docs` in that app.

## Local Development

From the repository root:

```bash
npm --prefix site ci
npm --prefix site run dev
```

Open the printed localhost URL and navigate to `/docs`.

## Validation

Run the production site build before changing navigation-sensitive files,
renaming pages, or editing MDX components:

```bash
npm --prefix site run build
```

The CI gate for docs changes is `.github/workflows/site-build.yml`.

## Adding New Pages

- Add or edit a `.mdx` or `.md` file under `docs/`.
- Navigation is derived from the content tree by `site/lib/docs.ts`.
- Keep generated API reference pages under `api-reference/` in sync with the
  docs generation workflow.
- If you add app-specific components or MDX behavior, implement them in `site/`
  and validate with the Next build.

## Hosting

The Vercel project should use `site` as its root directory. Do not attach
production domains or run a production deployment without explicit approval.
