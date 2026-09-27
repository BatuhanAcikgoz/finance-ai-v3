# Apex shadcn Theme + Sidebar Layout Refactor — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Keep tasks bite-sized (2-5 min). Each task ends with: edit → verify → commit.

**Goal:** Refactor `apps/dashboard/dist/` to look and feel like the **Apex shadcn** admin template — replace the top nav with a left sidebar, restyle every page with shadcn/design-token theming, deduplicate the JS/auth/sidebar boilerplate, and verify every page renders clean data without JS errors.

**Architecture:**
- `index.html` and 8 sibling pages share an inline `<aside class="app-sidebar">…</aside>` block injected by a single `side-nav.js` script (one place to update navigation).
- `styles.css` becomes a single source of design tokens (CSS variables in OKLCH for shadcn-grade color), grid layout primitives, and component classes (`.card`, `.btn`, `.badge`, `.input`, `.table`, `.kpi`, etc.).
- Duplicate JS (session/auth/fetch wrappers) consolidated into `ui.js`. `app.js` (1639 lines) and `latest-preview.js` keep only chart + portfolio-detail responsibilities.
- All page-specific JS remains in its `<name>.js` next to its `<name>.html`.

**Tech Stack:**
- Vanilla HTML/CSS/JS (no React, no Vite — we serve `dist/` via nginx in dashboard container)
- shadcn/ui design tokens (OKLCH colors, spacing, radius, font) copied as CSS variables
- lucide-style inline SVGs (already used in template) for icons
- No new npm dependencies (project already has Next.js 14 listed in `package.json`, but `dist/` is statically served)

---

## Assumptions

- We do not need React/SSR. The current `dist/` is plain HTML+CSS+JS served by nginx; keep that property.
- "side menu with collapsible groups" pattern from Apex is what the user means by "sidebar" — recreate it as a sticky left sidebar with 4 nav groups (Trading, Analytics, System, Admin).
- Color system: Apex uses OKLCH emerald/teal accent on a dark sidebar. We will match the same accent while preserving user's bilingual TR/EN labels.
- Tests: there is no existing playwright suite wired up. Use `curl` + manual `node --check` for verification.

---

## Task Breakdown

### Phase A — Theme tokens (foundation)

**Task A1: Rewrite styles.css header with shadcn design tokens**
File: `apps/dashboard/dist/styles.css`
Replace lines 1-80 (CSS variables block) with shadcn-grade tokens in OKLCH. Keep all existing component classes; only the tokens change so colors stay in sync across dark/light.
Verify: `node -e "console.log(require('fs').statSync('dist/styles.css').size)"` reports a sensible size (2.5KB - 4KB for the var block).
Commit: `style(tokens): rewrite CSS variables as shadcn OKLCH tokens`

**Task A2: Add sidebar primitives to styles.css**
Append at end of `styles.css`:
- `.app` becomes `display: grid; grid-template-columns: 260px 1fr; grid-template-rows: 64px 1fr; gap: 0; min-height: 100vh;`
- `.app-sidebar` — `grid-row: 1 / span 2; background: var(--sidebar); color: var(--sidebar-fg); padding: 16px; display: flex; flex-direction: column; gap: 4px; border-right: 1px solid var(--border);`
- `.app-topbar` — `grid-row: 1; grid-column: 2; height: 64px; display: flex; align-items: center; padding: 0 24px; border-bottom: 1px solid var(--border);`
- `.app-main` — `grid-row: 2; grid-column: 2; padding: 24px;`
- `.nav-group` — group wrapper with label + list of links
- `.nav-link` — `display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; color: var(--muted); transition: 120ms;`
- `.nav-link.is-active` — `background: var(--accent); color: var(--accent-fg);`
- `.nav-link:hover` — `background: var(--muted); color: var(--foreground);`
Verify: file size still ~30KB.
Commit: `style(sidebar): add sidebar primitives + main grid template`

**Task A3: Remove top-nav CSS duplicates from styles.css**
Search and delete every `.app-nav*`, `.nav-brand*`, `.nav-links*`, `.nav-right*`, `.last-updated*`, `.health-badge*` rule (moved to sidebar/topbar above).
Verify: `grep -E "\.app-nav|\.nav-brand|\.nav-links" dist/styles.css` returns 0 matches.
Commit: `style(sidebar): drop top-nav CSS now that sidebar owns primary nav`

### Phase B — Sidebar HTML partial

**Task B1: Create side-nav.js — shared sidebar injector**
Create `apps/dashboard/dist/side-nav.js`. Each page includes `<script src="side-nav.js?v=…" defer></script>` and the script:
- Reads `data-active-nav` attribute on `<body>` to set `is-active` on the right link.
- Injects an `<aside class="app-sidebar">` with 4 nav groups BEFORE the first child of `<div class="app">`.
- Injects a `<header class="app-topbar">` for breadcrumb + theme toggle + user menu.
- Owns the theme toggle (moved from inline `data-theme-toggle` handlers in every page).
- Call `window.FA.sideNav.mount({ activePage: 'overview' })` after `requireSession()` resolves.

Verify: `node --check side-nav.js` exits 0; load `index.html` server-side doesn't run JS but the JS itself parses.

Commit: `feat(sidebar): shared side-nav.js mounts the primary nav across pages`

**Task B2: Move theme-toggle from inline duplicate to side-nav.js**
Delete `data-theme-toggle` listener from `app.js` and every page's `<script>` block.
Commit: `refactor(sidebar): consolidate theme-toggle into side-nav.js`

### Phase C — Per-page migration (parallelizable)

Each task converts ONE page from top-nav layout to sidebar layout.

**Task C1: index.html** (overview/dashboard)
- Delete `<nav class="app-nav">…</nav>` block.
- Add `<script src="side-nav.js?v=…" defer></script>` before `ui.js`.
- Add `data-active-nav="overview"` to `<body>`.
- `<div class="app">` keeps the content but loses the inline nav.
Verify: `curl localhost:8080/index.html | grep -c 'class="app-nav"'` returns 0; sidebar link "Overview" rendered (curl can't run JS but the script tag is there).
Commit: `refactor(overview): migrate to shared sidebar layout`

**Task C2: decisions.html**
Same pattern, `data-active-nav="decisions"`.
Commit: `refactor(decisions): migrate to shared sidebar layout`

**Task C3: portfolio.html**
`data-active-nav="portfolio"`.
Commit: `refactor(portfolio): migrate to shared sidebar layout`

**Task C4: alerts.html**
`data-active-nav="alerts"`.
Commit: `refactor(alerts): migrate to shared sidebar layout`

**Task C5: settings.html**
`data-active-nav="settings"`.
Commit: `refactor(settings): migrate to shared sidebar layout`

**Task C6: admin.html**
`data-active-nav="admin"`. Admin uses `bindSessionBar` which currently draws inside the page — move that block into a `<div data-session-slot>` so the topbar's user menu slot can host it.
Commit: `refactor(admin): migrate to shared sidebar layout + session slot`

**Task C7: decision-detail.html**
`data-active-nav="decisions"`. This page currently has its own inline header bar — keep the article's title bar as content but drop the duplicated nav.
Commit: `refactor(decision-detail): migrate to shared sidebar layout`

**Task C8: system-health.html**
`data-active-nav="system"`.
Commit: `refactor(system-health): migrate to shared sidebar layout`

### Phase D — JS deduplication

**Task D1: Audit duplicate code in admin.js, app.js, alerts.js, decisions.js, decision-detail.js, portfolio.js, settings.js**
Look for: `window.FA.ui.fetchAdmin`, `requireSession()`, manual fetch wrappers, theme-toggle handlers, logout handlers, header binding, theme bootstrap script blocks.
Compile a list of shared primitives that survive (cookie check, requireSession, toast, format helpers) — these all live in `ui.js` already — and delete the duplicates in each page JS.
Verify: `grep -c "requireSession\|fetchJSON\|fetchAdmin" dist/*.js` should only return 1 (ui.js).
Commit: `chore(dedup): remove duplicate session/fetch wrappers from page JS`

**Task D2: Extract session-bar / bindSessionBar logic from admin.js into side-nav.js**
Move user-menu rendering out of admin.js into a `window.FA.sideNav.userMenu(session)` slot. Drop the `<session-bar>` markup from admin.html.
Verify: admin.html no longer contains the inline username pill.
Commit: `refactor(sidebar): host session info in topbar user-menu`

### Phase E — Verification (cross-check every page)

**Task E1: Build + restart dashboard image**
Run `docker compose --env-file .env.docker build dashboard --no-cache && docker compose --env-file .env.docker up -d --force-recreate dashboard`.
Verify: `docker ps --filter name=dashboard` shows "Up".
Commit: N/A (build only).

**Task E2: curl each page → 200 with no error markers**
Loop over all 9 HTML pages. Run `curl -s http://localhost:8080/<page>.html -w "%{http_code} %{size_download}\n" -o /dev/null`. Expect 9 lines of "200 …".

**Task E3: `node --check` every JS file**
Run `node --check dist/ui.js dist/side-nav.js dist/app.js dist/admin.js dist/login.js dist/alerts.js dist/decisions.js dist/portfolio.js dist/settings.js dist/decision-detail.js dist/system-health.js dist/latest-preview.js`. Expect all 0.

**Task E4: Visual smoke test — headless browser snapshot**
Use `playwright` or `python+headless-chromium` to:
- Visit each page after `POST /v1/auth/login admin/admin` (cookie set).
- Take a screenshot.
- Assert no `console.error` fires.
- Assert the sidebar shows the expected active link.
Save screenshots into `infra/docker/screenshots/` so the user can review without re-running.
Verify: 9 PNGs created, each < 250KB.

**Task E5: API smoke — every page's primary endpoint returns 200**
For each page note the primary endpoint (decisions → /v1/decisions/recent, portfolio → /v1/portfolio/snapshot, etc.), curl with the auth cookie, expect 200.
Verify: 9/9 endpoints return 200.

### Phase F — Cleanup

**Task F1: Drop styles.css rules only referenced by legacy `.app-nav*`**
After sidebar migration, search styles.css for `.app-nav`, `.nav-brand*`, `.nav-links`, `.nav-right*`, `.health-badge` rules. Delete.
Commit: `chore(style): prune legacy top-nav CSS rules`

**Task F2: Update nginx.conf cache-bust comment**
Add a comment near the `expires 1d` line reminding future maintainers to bump the `?v=` query on every stylesheet/script <link>/<script> when CSS tokens change.
Commit: `docs(nginx): remind to bump cache-bust on style changes`

---

## Files Likely To Change

| File | Action | Why |
|---|---|---|
| `apps/dashboard/dist/styles.css` | rewrite | shadcn tokens + sidebar primitives |
| `apps/dashboard/dist/side-nav.js` | create | shared sidebar injector |
| `apps/dashboard/dist/index.html` | modify | drop top nav, add data-active-nav |
| `apps/dashboard/dist/decisions.html` | modify | drop top nav |
| `apps/dashboard/dist/portfolio.html` | modify | drop top nav |
| `apps/dashboard/dist/alerts.html` | modify | drop top nav |
| `apps/dashboard/dist/settings.html` | modify | drop top nav |
| `apps/dashboard/dist/admin.html` | modify | drop top nav + bindSessionBar wrapper |
| `apps/dashboard/dist/decision-detail.html` | modify | drop top nav |
| `apps/dashboard/dist/system-health.html` | modify | drop top nav |
| `apps/dashboard/dist/app.js` | modify | remove duplicate auth/theme-toggle fetches |
| `apps/dashboard/dist/admin.js` | modify | remove bindSessionBar |
| `apps/dashboard/dist/login.html` | **not touched** | login has its own layout |

Estimated diff size: 12 files, ~1500 lines net change (styles.css rewrite largest).

---

## Risks & Tradeoffs

1. **Risk:** Sidebar layout is wider than top nav — on a 1280×800 viewport, content area shrinks by 260px. Mitigation: collapse sidebar to icons-only on `<1024px` (responsive).
2. **Risk:** shadcn OKLCH colors don't render in Firefox < 113. Mitigation: provide `oklch(... / 1.0)` as fallback by also defining `#hex` first, then OKLCH.
3. **Risk:** All 9 pages must update consistently or the design system breaks. Mitigation: `side-nav.js` is the single source — if it works for index.html, all other pages that include it work.
4. **Tradeoff:** We keep plain HTML+CSS+JS (no React). The plan sacrifices shadcn's `cn()` helper, but a 10-line JS equivalent covers tailwind-merge substitution.
5. **Open question:** Should admin link be visible to non-admin users? Current behavior: hidden when no admin token. Keep current behavior — admin role-check stays.

---

## Acceptance Criteria

- [ ] Every HTML page loads from `http://localhost:8080/<page>.html` with HTTP 200
- [ ] Browser console reports 0 errors when loading any page (after login)
- [ ] Sidebar shows 4 groups: Trading, Analytics, System, Admin (admin only if user role = admin)
- [ ] Topbar shows breadcrumb + theme toggle + user-menu on every page
- [ ] `node --check` exits 0 on all `.js` files
- [ ] `grep -c 'app-nav' dist/styles.css` returns 0 (legacy top-nav CSS gone)
- [ ] `grep -c 'data-theme-toggle' dist/*.js` returns ≤ 1 (only side-nav.js handles it)
- [ ] All 9 user-reported "Content at file:///" errors from previous session cleared
- [ ] Visual identity (sidebar + cards + tables + accents) matches Apex shadcn screenshots in spirit (collapsed sidebar, dark navy, emerald/teal accent, rounded 12px corners)
