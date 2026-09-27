// ui.js — single source of truth for cross-page behaviour in the dashboard.
//
// Replaces the previous X-Admin-Token / localStorage pattern. Auth is now
// an HttpOnly cookie issued by POST /v1/auth/login. Pages that need
// authentication call window.FA.requireSession() at startup — it returns
// 302-style redirect to /login.html if the session is missing/expired.
//
// Surface:
//   window.FA.requireSession()               → redirect to login if no session
//   window.FA.api.fetchJSON(path, opts?)     → fetch + JSON parse + 401 handling
//   window.FA.api.fetchAdmin(path, opts?)    → /api/v1/admin/* (cookie-authed)
//   window.FA.toast.show(msg, kind?)         → ephemeral toast
//   window.FA.format.num(x) / date(x) / money(x)
//   window.FA.session.whoami()               → {username, role, must_change_password}
//   window.FA.session.signOut()              → POST /v1/auth/logout
//
(() => {
  "use strict";

  // Always resolve the API base against the *current* document origin.
  // Using a hard-coded '/api/v1' relative path collides when the page
  // is reached through a different port (e.g. http://127.0.0.1:80/foo
  // vs http://127.0.0.1:8080/foo) or via a hostname proxy — the
  // browser would otherwise re-resolve the path against an unwanted
  // origin and trigger CORS / 127.0.0.1 (no port) surprises.
  const API_BASE = (typeof window !== "undefined" && window.location
                    ? window.location.origin + "/api/v1"
                    : "/api/v1");
  const LOGIN_URL = (typeof window !== "undefined" && window.location
                    ? window.location.origin + "/login.html"
                    : "/login.html");

  async function whoami() {
    try {
      const r = await fetch(API_BASE + "/auth/me", { credentials: "same-origin" });
      if (r.status === 401) return null;
      if (!r.ok) return null;
      return await r.json();
    } catch (_) {
      return null;
    }
  }

  async function requireSession() {
    const me = await whoami();
    if (me) return me;
    const target = location.pathname + location.search;
    const url = LOGIN_URL + (target && target !== LOGIN_URL ? "?next=" + encodeURIComponent(target) : "");
    location.replace(url);
    return null;
  }

  async function signOut() {
    try {
      await fetch(API_BASE + "/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      });
    } catch (_) {
      // ignore — we're heading out anyway
    }
    location.replace(LOGIN_URL);
  }

  async function fetchJSON(path, opts) {
    const o = Object.assign({ credentials: "same-origin", headers: {} }, opts || {});
    if (o.body && typeof o.body !== "string" && !(o.body instanceof FormData)) {
      o.headers["Content-Type"] = "application/json";
      o.body = JSON.stringify(o.body);
    }
    const r = await fetch(API_BASE + path, o);
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (_) { data = null; }
    if (r.status === 401) {
      const target = location.pathname + location.search;
      const url = LOGIN_URL + (target && target !== LOGIN_URL ? "?next=" + encodeURIComponent(target) : "");
      location.replace(url);
      throw new Error("session expired");
    }
    if (!r.ok) {
      const detail = (data && (data.detail || data.error)) || r.statusText || "request failed";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  async function fetchAdmin(path, opts) {
    return fetchJSON("/admin/" + String(path).replace(/^\//, ""), opts);
  }

  function ensureToastHost() {
    let host = document.getElementById("fa-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "fa-toast-host";
      host.className = "fa-toast-host";
      document.body.appendChild(host);
    }
    return host;
  }
  function showToast(msg, kind) {
    const host = ensureToastHost();
    const el = document.createElement("div");
    el.className = "fa-toast fa-toast-" + (kind || "info");
    el.textContent = msg;
    host.appendChild(el);
    requestAnimationFrame(() => el.classList.add("fa-toast-in"));
    setTimeout(() => {
      el.classList.remove("fa-toast-in");
      el.classList.add("fa-toast-out");
      setTimeout(() => el.remove(), 200);
    }, 3500);
  }

  function fmtNum(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
    return Number(n).toLocaleString("en-US", { maximumFractionDigits: 4 });
  }
  function fmtDate(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return "—";
      return d.toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
    } catch (_) {
      return "—";
    }
  }
  function fmtMoney(n, ccy) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return v.toLocaleString("en-US", { style: "currency", currency: ccy || "USD" });
  }

  window.FA = window.FA || {};
  window.FA.requireSession = requireSession;
  window.FA.session = { whoami, signOut };
  window.FA.api = { fetchJSON, fetchAdmin };
  window.FA.toast = { show: showToast };
  window.FA.format = { num: fmtNum, date: fmtDate, money: fmtMoney };

  document.addEventListener("DOMContentLoaded", () => {
    if (document.body && document.body.dataset && document.body.dataset.requireSession !== undefined) {
      requireSession();
    }
    // Mount the shared sidebar + topbar if side-nav.js is on the page.
    // It's a no-op when the script didn't load (e.g. login.html).
    if (window.FA && window.FA.sideNav && typeof window.FA.sideNav.mount === "function") {
      try { window.FA.sideNav.mount(); } catch (e) { /* sidebar is decorative, never block page render */ }
    }
  });
})();
