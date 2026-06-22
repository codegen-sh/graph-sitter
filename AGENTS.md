# Agent Notes

## Frontend

- The Vercel app lives in `site/`.
- Vercel is configured by `site/vercel.json`; preview builds skip full docs prerendering, and the ignored build step skips builds unless `site/` or `docs/` changed.
- Use Aura Dark from `daltonmenezes/aura-theme` for frontend dark mode and code surfaces. Core palette: background `#15141b`, foreground `#edecee`, muted `#6d6d6d`, purple `#a277ff`, green `#61ffca`, orange `#ffca85`, pink `#f694ff`, blue `#82e2ff`, red `#ff6767`.
- Keep docs syntax highlighting aligned with the Aura Dark palette.
- Use Node 22 for local site commands: `PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH" npm --prefix site run build`.
