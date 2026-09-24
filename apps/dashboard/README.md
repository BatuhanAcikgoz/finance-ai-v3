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
│   ├── index.html        # home — symbols, decisions preview, KPIs
│   ├── decisions.html    # decisions list (filters + table)
│   ├── decision-detail.html # single decision: evidence trace, compliance, etc.
│   ├── app.js            # shared helpers + home-page renderers (window.FA namespace)
│   ├── decisions.js      # decisions-list page logic
│   ├── decision-detail.js # decision-detail page logic
│   ├── latest-preview.js # home-page "Latest decision" highlight
│   └── favicon.svg       # inline-friendly green hexagon mark
├── src/                  # Next.js UI prototype (WIP, not built)
├── package.json          # Next.js manifest (kept for the WIP source tree)
└── README.md             # this file
```

## Pages & navigation

- **`/` (index.html)** — overview: symbols, KPI strip, "Latest decision" highlight,
  alerts, market snapshot. Top-nav links to **Kararlar / Decisions**.
- **`/decisions.html`** — paginated list of every decision with filters:
  date range, ticker (datalist from `/v1/market/symbols`), action,
  confidence slider (placeholder), and compliance status. Row click → detail.
- **`/decision-detail.html?id=…`** — full evidence trace, portfolio context,
  compliance audit, prompt-version snapshot, and similar past decisions.

All three pages share helpers exposed on `window.FA` from `app.js`:

- `fetchJson`, `fetchPost`, `normalizeList`
- `renderActionBadge`, `renderComplianceBadge`, `renderConfidenceMeter`,
  `renderEvidenceCard`, `renderTable`
- `renderTRT` (Turkish-local datetime), `getQueryParam`
- `detailUrl(id)`, `decisionsUrl(ticker)`, `shortId(uuid)`
- `parseJsonb(v)` — handles api-gateway's stringified jsonb
- `attachRefreshLoop(fn, ms)`, `hardRefresh()`

### Filter behaviour

`/v1/decisions/recent` supports `ticker` and `compliance_status` server-side.
Date range, action, and confidence are applied **client-side** over the
returned list (server caps at 200 rows). The confidence slider and date
controls render normally today so the UI is exercised, but the date range and
confidence will move server-side once endpoints support them.

### Latest decision preview

`latest-preview.js` polls `/v1/decisions/recent?limit=1` every 30s and fills
the "Son karar / Latest" card on the home page. Hidden when there are zero
decisions.

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
