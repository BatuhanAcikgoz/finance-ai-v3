// side-nav.js — shared sidebar + topbar injector for the dashboard.
//
// Loaded AFTER ui.js (which exposes window.FA) and BEFORE page-specific JS.
// Pages do not need any sidebar markup — this script prepends the <aside>
// and topbar <header> into the first <div class="app"> (or <body> as a
// fallback) on demand.
//
// Public API:
//   window.FA.sideNav.mount(opts?)        — build + insert sidebar + topbar
//   window.FA.sideNav.sessionBar(info?)   — refresh user-menu avatar/name/role
//   window.FA.sideNav.setActive(name?)    — toggle the is-active nav-link
//
// opts:
//   active?   string  — nav-link to mark is-active (defaults to body[data-active-nav]
//                       or the path->page map below)
//   session?  object  — {username, role} used for the user menu
//
(() => {
  "use strict";

  if (typeof window === "undefined") return;
  window.FA = window.FA || {};

  // ─────────────────────────────────────────────────────────────────────
  // Templates
  // ─────────────────────────────────────────────────────────────────────

  const SIDEBAR_HTML = `
<aside class="app-sidebar" aria-label="primary">
  <div class="sidebar-brand">
    <span class="sidebar-brand-mark">F</span>
    <div>
      Finance AI V3
      <small>Trading · Analytics · Admin</small>
    </div>
  </div>

  <div class="nav-group" data-group="trading">
    <span class="nav-group-label">Trading / Trading</span>
    <a class="nav-link" href="index.html" data-nav="overview">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      <span class="nav-link-label">Genel Bakış · Overview</span>
    </a>
    <a class="nav-link" href="decisions.html" data-nav="decisions">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
      <span class="nav-link-label">Kararlar · Decisions</span>
    </a>
    <a class="nav-link" href="portfolio.html" data-nav="portfolio">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
      <span class="nav-link-label">Portföy · Portfolio</span>
    </a>
    <a class="nav-link" href="alerts.html" data-nav="alerts">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      <span class="nav-link-label">Uyarılar · Alerts</span>
    </a>
  </div>

  <div class="nav-group" data-group="analytics">
    <span class="nav-group-label">Analiz · Analytics</span>
    <a class="nav-link" href="decision-detail.html" data-nav="decision-detail">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <span class="nav-link-label">Karar Detayı · Decision Detail</span>
    </a>
    <a class="nav-link" href="system-health.html" data-nav="system-health">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      <span class="nav-link-label">Sistem Sağlığı · System Health</span>
    </a>
  </div>

  <div class="nav-group" data-group="system">
    <span class="nav-group-label">Sistem · System</span>
    <a class="nav-link" href="settings.html" data-nav="settings">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      <span class="nav-link-label">Ayarlar · Settings</span>
    </a>
  </div>

  <div class="nav-group" data-group="admin" data-admin-only>
    <span class="nav-group-label">Yönetim · Admin</span>
    <a class="nav-link" href="admin.html" data-nav="admin">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      <span class="nav-link-label">Yönetim Paneli · Admin</span>
    </a>
  </div>
</aside>
`;

  const TOPBAR_HTML = `
<header class="app-topbar">
  <button class="mobile-menu-btn" aria-label="Menu" type="button">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </button>
  <div class="topbar-breadcrumb" id="topbar-breadcrumb">
    <a href="index.html">Finance AI V3</a><span class="bc-sep">/</span><span data-active-label>—</span>
  </div>
  <div class="topbar-right">
    <button class="theme-toggle" data-theme-toggle aria-label="Tema / Theme" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M4.93 19.07l1.41-1.41"/><path d="M17.66 6.34l1.41-1.41"/></svg>
    </button>
    <div class="user-menu" id="user-menu" tabindex="0" role="button" aria-haspopup="menu" aria-expanded="false">
      <div class="user-menu-avatar" id="user-menu-avatar">?</div>
      <span class="user-menu-info">
        <span id="user-menu-name">Account</span>
        <span class="user-menu-role" id="user-menu-role" hidden></span>
      </span>
      <div class="user-menu-dropdown" id="user-menu-dropdown" role="menu" hidden>
        <button type="button" class="user-menu-item" data-action="signout" role="menuitem">Çıkış · Sign out</button>
      </div>
    </div>
  </div>
</header>
`;

  // ─────────────────────────────────────────────────────────────────────
  // Path → nav-key map
  // ─────────────────────────────────────────────────────────────────────

  const PAGE_MAP = [
    { test: /index\.html$/,              key: "overview" },
    { test: /decisions\.html$/,          key: "decisions" },
    { test: /decision-detail\.html$/,    key: "decision-detail" },
    { test: /portfolio\.html$/,          key: "portfolio" },
    { test: /alerts\.html$/,             key: "alerts" },
    { test: /system-health\.html$/,      key: "system-health" },
    { test: /settings\.html$/,           key: "settings" },
    { test: /admin\.html$/,              key: "admin" },
  ];

  function resolveActiveFromPath(p) {
    if (!p) return null;
    for (const m of PAGE_MAP) {
      if (m.test.test(p)) return m.key;
    }
    return null;
  }

  function resolveActive() {
    const ds = (document.body && document.body.dataset) || {};
    if (ds.activeNav) return ds.activeNav;
    const fromPath = resolveActiveFromPath(window.location && window.location.pathname);
    return fromPath || null;
  }

  // Read the human-readable label of the currently active nav link.
  function activeLabel() {
    const link = document.querySelector(".app-sidebar .nav-link.is-active .nav-link-label");
    if (link) return link.textContent.trim();
    return "—";
  }

  // ─────────────────────────────────────────────────────────────────────
  // Helpers
  // ─────────────────────────────────────────────────────────────────────

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === "class") e.className = attrs[k];
        else if (k === "html") e.innerHTML = attrs[k];
        else if (k === "text") e.textContent = attrs[k];
        else if (k === "hidden") { if (attrs[k]) e.hidden = true; }
        else e.setAttribute(k, attrs[k]);
      }
    }
    if (children) {
      for (const c of children) {
        if (c == null) continue;
        e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
      }
    }
    return e;
  }

  function findAppRoot() {
    return document.querySelector(".app") || document.body;
  }

  function ensureAppWrapper() {
    let app = document.querySelector(".app");
    if (app) return { app, created: false };
    // No .app wrapper — create one and move existing children into it.
    app = el("div", { class: "app" });
    const body = document.body;
    while (body.firstChild) {
      const node = body.firstChild;
      if (node.nodeType === 1 && node.tagName === "SCRIPT") {
        // leave <script> tags where they are (they must stay under <body>)
        body.removeChild(node);
        body.appendChild(node);
        continue;
      }
      app.appendChild(node);
    }
    body.appendChild(app);
    return { app, created: true };
  }

  function safeSession() {
    try {
      const FA = window.FA || {};
      if (FA.session && typeof FA.session.whoami === "function") {
        return FA.session.whoami();
      }
    } catch (_) { /* swallow */ }
    return Promise.resolve(null);
  }

  function detectAdmin(session) {
    if (session && typeof session === "object" && session.role) {
      return session.role === "admin";
    }
    // Fallback — allow pages to publish their role via body dataset.
    const ds = (document.body && document.body.dataset) || {};
    if (ds.userRole) return ds.userRole === "admin";
    return false;
  }

  function currentTheme() {
    const dt = document.documentElement.getAttribute("data-theme");
    if (dt === "light" || dt === "dark") return dt;
    try {
      const v = localStorage.getItem("finance-ai.theme");
      if (v === "light" || v === "dark") return v;
    } catch (_) { /* ignore */ }
    return "dark";
  }

  function persistTheme(t) {
    try { localStorage.setItem("finance-ai.theme", t); } catch (_) { /* ignore */ }
  }

  // ─────────────────────────────────────────────────────────────────────
  // Theme + user-menu wiring
  // ─────────────────────────────────────────────────────────────────────

  function bindThemeToggle(btn) {
    if (!btn) return;
    btn.addEventListener("click", () => {
      const FA = window.FA || {};
      if (FA.theme && typeof FA.theme.toggle === "function") {
        try { FA.theme.toggle(); return; } catch (_) { /* fall through */ }
      }
      const next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      persistTheme(next);
      if (FA.toast && typeof FA.toast.show === "function") {
        FA.toast.show(next === "dark" ? "Karanlık tema · Dark" : "Aydınlık tema · Light", "info");
      }
    });
  }

  function bindUserMenu(root) {
    if (!root) return;
    const dd = root.querySelector("#user-menu-dropdown");
    const setOpen = (open) => {
      if (!dd) return;
      dd.hidden = !open;
      root.setAttribute("aria-expanded", open ? "true" : "false");
      root.classList.toggle("is-open", !!open);
    };

    root.addEventListener("click", (ev) => {
      ev.stopPropagation();
      setOpen(dd && dd.hidden);
    });
    root.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        setOpen(dd && dd.hidden);
      } else if (ev.key === "Escape") {
        setOpen(false);
      }
    });
    document.addEventListener("click", (ev) => {
      if (!root.contains(ev.target)) setOpen(false);
    });

    if (dd) {
      dd.addEventListener("click", async (ev) => {
        const t = ev.target.closest("[data-action='signout']");
        if (!t) return;
        ev.preventDefault();
        const FA = window.FA || {};
        if (FA.session && typeof FA.session.signOut === "function") {
          try { await FA.session.signOut(); } catch (_) { /* ignore */ }
        }
        // Hard fallback — never leave the user stranded.
        try { location.replace("/login.html"); }
        catch (_) { location.href = "/login.html"; }
      });
    }
  }

  function bindMobileMenu(btn, sidebar) {
    if (!btn || !sidebar) return;
    btn.addEventListener("click", () => {
      const open = !sidebar.classList.contains("is-open");
      sidebar.classList.toggle("is-open", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      document.documentElement.classList.toggle("sidebar-open", open);
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // Public: mount / sessionBar / setActive
  // ─────────────────────────────────────────────────────────────────────

  function applyActive(key) {
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar) return;
    sidebar.querySelectorAll(".nav-link").forEach((a) => {
      a.classList.toggle("is-active", a.dataset.nav === key);
    });
    const lbl = document.querySelector("[data-active-label]");
    if (lbl) lbl.textContent = activeLabel();
  }

  function hideAdminOnly() {
    document.querySelectorAll("[data-admin-only]").forEach((el) => {
      el.style.display = "none";
    });
  }

  function showAdminOnly() {
    document.querySelectorAll("[data-admin-only]").forEach((el) => {
      el.style.display = "";
    });
  }

  function renderSessionBar(session) {
    const av = document.getElementById("user-menu-avatar");
    const nm = document.getElementById("user-menu-name");
    const rl = document.getElementById("user-menu-role");
    const menu = document.getElementById("user-menu");
    if (!menu) return;
    const dd = menu.querySelector("#user-menu-dropdown");
    if (session && session.username) {
      const letter = String(session.username).trim().charAt(0).toUpperCase() || "?";
      if (av) av.textContent = letter;
      if (nm) nm.textContent = session.username;
      if (rl) {
        if (session.role) {
          rl.textContent = session.role;
          rl.hidden = false;
        } else {
          rl.hidden = true;
        }
      }
      if (dd) {
        dd.innerHTML = '<button type="button" class="user-menu-item" data-action="signout" role="menuitem">Çıkış · Sign out</button>';
      }
    } else {
      // Unauthenticated — collapse to a plain "Account" link to /login.html.
      if (av) av.textContent = "?";
      if (nm) nm.textContent = "Account";
      if (rl) rl.hidden = true;
      if (dd) dd.hidden = true;
      menu.removeAttribute("tabindex");
      menu.removeAttribute("role");
      menu.removeAttribute("aria-haspopup");
      // Make the whole menu behave as a link.
      menu.addEventListener("click", () => {
        try { location.href = "/login.html"; } catch (_) { /* no-op */ }
      }, { once: true });
    }
  }

  function mount(opts) {
    if (typeof document === "undefined") return;
    const run = () => {
      // Wrap body contents if the page doesn't already have <div class="app">.
      const { app } = ensureAppWrapper();

      // Insert sidebar + topbar (don't double-mount).
      if (!app.querySelector(".app-sidebar")) {
        const tmp = document.createElement("div");
        tmp.innerHTML = SIDEBAR_HTML.trim();
        const sidebar = tmp.firstChild;
        app.insertBefore(sidebar, app.firstChild);
      }
      if (!app.querySelector(".app-topbar")) {
        const tmp2 = document.createElement("div");
        tmp2.innerHTML = TOPBAR_HTML.trim();
        const topbar = tmp2.firstChild;
        const sidebar = app.querySelector(".app-sidebar");
        app.insertBefore(topbar, sidebar ? sidebar.nextSibling : app.firstChild);
      }

      // Hide "Decision Detail" if we're not actually on a decision-detail URL.
      const ddLink = app.querySelector(".nav-link[data-nav='decision-detail']");
      if (ddLink) {
        const onDetail = /decision-detail\.html/.test(window.location.pathname || "");
        ddLink.style.display = onDetail ? "" : "none";
      }

      // Wire interactions.
      bindThemeToggle(app.querySelector("[data-theme-toggle]"));
      bindUserMenu(app.querySelector("#user-menu"));
      bindMobileMenu(app.querySelector(".mobile-menu-btn"), app.querySelector(".app-sidebar"));

      // Active state.
      const requested = (opts && opts.active) || resolveActive();
      if (requested) applyActive(requested);

      // Admin gate.
      const session = (opts && opts.session) || null;
      if (detectAdmin(session)) showAdminOnly(); else hideAdminOnly();

      // If no session was supplied, try the async whoami path.
      if (!session) {
        safeSession().then((me) => {
          if (me) {
            if (detectAdmin(me)) showAdminOnly(); else hideAdminOnly();
            renderSessionBar(me);
          } else {
            renderSessionBar(null);
          }
        }).catch(() => { renderSessionBar(null); });
      } else {
        renderSessionBar(session);
      }
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", run, { once: true });
    } else {
      run();
    }
  }

  function sessionBar(session) {
    // Re-render the user-menu only (no sidebar mutation).
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => renderSessionBar(session || null), { once: true });
      return;
    }
    renderSessionBar(session || null);
    // Admin gate updates as well — if a non-admin session becomes available,
    // we want to hide the admin nav; if admin, show it.
    if (detectAdmin(session || null)) showAdminOnly(); else hideAdminOnly();
  }

  function setActive(name) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => applyActive(name), { once: true });
      return;
    }
    applyActive(name || null);
  }

  window.FA.sideNav = { mount, sessionBar, setActive };
})();
