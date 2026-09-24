# Dashboard

Static, single-page dashboard for **Finance AI V3**.

## Status

The dashboard is served as **static HTML + vanilla JS** — no build step, no Node.js runtime
required at deploy time. Nginx serves `dist/` directly and reverse-proxies `/api/*` to the
`api-gateway` service.

The legacy Next.js scaffolding under `src/` is **work-in-progress** and intentionally not
built by CI. The current production artifact is `dist/`.

## Layout

```
apps/dashboard/
├── dist/                 # ← what nginx serves
│   ├── index.html        # semantic HTML5, ~250 lines, inline CSS using Hermes palette
│   ├── app.js            # vanilla JS — fetch + render, auto-refresh every 30s
│   └── favicon.svg       # inline-friendly green hexagon mark
├── src/                  # Next.js UI prototype (WIP, not built)
├── package.json          # Next.js manifest (kept for the WIP source tree)
└── README.md             # this file
```

## Preview locally

```bash
# from repo root
cd apps/dashboard/dist
python -m http.server 8181
# → http://localhost:8181
```

Note: when previewing with `python -m http.server`, browser fetches to `/api/*` will 404.
Either run the full stack (`make up` from the repo root) or stub `/api` responses
locally — the dashboard degrades gracefully and renders with fallback data if the
api-gateway is unreachable.

## API contract

The dashboard expects the api-gateway to expose:

| Endpoint                                 | Purpose                          |
|------------------------------------------|----------------------------------|
| `GET /api/health`                        | Health badge                     |
| `GET /api/v1/market/symbols`             | Symbols table                    |
| `GET /api/v1/market/symbols/{s}/bars`    | OHLCV bars (sparkline)           |
| `GET /api/v1/decisions/recent`           | Recent decisions list            |

Payloads may be either a JSON array or `{ "items": [...] }` / `{ "symbols": [...] }` /
`{ "decisions": [...] }` envelopes.

## Why static?

- **Zero build.** No `pnpm install`, no `next build`, no Webpack, no Vite. Drop the
  `dist/` folder behind any web server.
- **No CDN.** No React, no Tailwind, no chart library — only ~10 KB of vanilla JS
  and inline CSS. Self-contained and air-gap friendly.
- **Same-origin proxy.** Nginx serves the page and forwards `/api/*` to api-gateway:
  no CORS configuration, no separate origin.

## Roadmap

- Replace fallback datasets with live api-gateway responses as routes come online.
- Add WebSocket streaming for intraday tick updates.
- Move sparkline to a small Canvas renderer once per-symbol bar payloads exceed ~500 points.
