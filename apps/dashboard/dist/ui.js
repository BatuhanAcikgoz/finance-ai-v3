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

  // ── Back-compat aliases for older per-page scripts written before the
  // api/toast namespace refactor. These keep returning sensible results
  // even when the call shape differs (e.g. fetchJson(url, opts) instead
  // of api.fetchJSON(url, opts)).
  // Legacy fetchJson: built before params-as-object was supported — so we
  // synthesize ?key=value pairs and forward.
  window.FA.fetchJson = function (url, opts) {
    if (opts && opts.params && typeof opts.params === "object") {
      const qs = Object.entries(opts.params)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => encodeURIComponent(k) + "=" + encodeURIComponent(v))
        .join("&");
      if (qs && url.indexOf("?") === -1) url = url + "?" + qs;
    }
    return fetchJSON(url, opts);
  };
  window.FA.fetchAdmin = function (url, opts) { return fetchAdmin(url, opts); };
  window.FA.API_BASE = (typeof window !== "undefined" && window.location
                       ? window.location.origin + "/api"
                       : "/api");

  window.FA.toast = { show: showToast };
  // Older sign:   ui.toast("Hello", "info")
  // New sign:     toast.show("Hello", "info")
  // Support both names + a 2-arg shortcut.
  window.FA.toast.show  = showToast;
  window.FA.toast.error = (msg) => showToast(msg, "error");
  window.FA.toast.warn  = (msg) => showToast(msg, "warning");
  window.FA.toast.info  = (msg) => showToast(msg, "info");
  window.FA.toast.success = (msg) => showToast(msg, "success");
  // Legacy shim — some pages still call `FA.ui.toast('kind', 'msg')`.
  window.FA.ui = window.FA.ui || {};
  window.FA.ui.toast = showToast;
  window.FA.ui.fetchAdmin = fetchAdmin;

  // ── Page-helper utilities shared across all sub-pages. Centralized here
  // so decisions.js / decision-detail.js / latest-preview.js / portfolio.js
  // / alerts.js / system-health.js don't need app.js to be loaded.
  window.FA.getQueryParam = function (name) {
    try {
      const s = window.location.search || "";
      if (!s || s.charAt(0) !== "?") return null;
      const usp = new URLSearchParams(s);
      return usp.get(name);
    } catch (_) { return null; }
  };
  window.FA.attachRefreshLoop = function (fn, intervalMs) {
    const ms = intervalMs || 30000;
    const run = () => {
      try { Promise.resolve(fn()).catch(() => { /* swallow */ }); }
      catch (_) { /* swallow */ }
    };
    run();
    const h = setInterval(run, ms);
    try { window.addEventListener("pagehide", () => clearInterval(h)); } catch (_) {}
    return h;
  };
  // Best-effort WS connect — older pages expect `window.FA.connectWs()`.
  // Returns null so call sites don't crash on undefined.
  window.FA.connectWs = function () { return null; };

  window.FA.format = { num: fmtNum, date: fmtDate, money: fmtMoney };

  // ---- Shared render helpers (lifted from app.js IIFE#2) -----------------
  // These were previously only exposed when app.js was on the page. The
  // sub-pages (decisions.js, decision-detail.js, latest-preview.js, etc.)
  // call window.FA.renderActionBadge / renderTable / renderEvidenceCard
  // etc., so we re-host the same pure-function bodies here. If app.js
  // loads later, its `Object.assign(window.FA, FA)` is a no-op for these
  // names because the values are byte-identical.

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function fmtNum(n, digits) {
    if (n === null || n === undefined || n === "" || isNaN(Number(n))) return "—";
    var d = (digits === undefined) ? 2 : digits;
    return Number(n).toLocaleString("en-US", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }
  function fmtTime(d) {
    try {
      var dt = (d instanceof Date) ? d : new Date(d);
      if (isNaN(dt.getTime())) return "";
      return dt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (e) { return ""; }
  }
  function fmtVol(n) {
    if (n === null || n === undefined || n === "" || isNaN(Number(n))) return "—";
    n = Number(n);
    if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(2) + "K";
    return String(Math.round(n));
  }
  function fmtTRY(n, digits) {
    if (n === null || n === undefined || n === "" || isNaN(Number(n))) return "—";
    var d = (digits === undefined) ? 2 : digits;
    var s = Number(n).toLocaleString("de-DE", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
    return "₺" + s;
  }
  function fmtPct(n) {
    if (n === null || n === undefined || n === "" || isNaN(Number(n))) return { text: "—", cls: "neutral", sign: "" };
    var v = Number(n);
    var sign = v >= 0 ? "+" : "";
    var cls = v >= 0 ? "pos" : "neg";
    return { text: sign + v.toFixed(2) + "%", cls: cls, sign: sign, val: v };
  }
  function normalizeList(data) {
    if (Array.isArray(data)) return data;
    if (data && typeof data === "object") {
      for (var k in data) {
        if (Array.isArray(data[k])) return data[k];
      }
    }
    return [];
  }
  function parseJsonb(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === "object") return v;
    if (typeof v !== "string") return v;
    var s = v.trim();
    if (!s || s === "null" || s === "undefined") return null;
    if (s.charAt(0) !== "{" && s.charAt(0) !== "[") return null;
    try { return JSON.parse(s); } catch (e) { return null; }
  }
  function shortId(id) {
    if (!id) return "";
    return String(id).replace(/-/g, "").slice(0, 8);
  }
  function detailUrl(id) {
    return "decision-detail.html?id=" + encodeURIComponent(id);
  }
  function decisionsUrl(ticker) {
    return ticker ? ("decisions.html?ticker=" + encodeURIComponent(ticker)) : "decisions.html";
  }
  function renderTRT(iso) {
    if (!iso) return "—";
    var d = (typeof iso === "string") ? new Date(iso) : (iso instanceof Date ? iso : null);
    if (!d || isNaN(d.getTime())) return String(iso);
    try {
      var months = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
                    "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
      var dd = d.getDate();
      var mm = months[d.getMonth()];
      var yy = d.getFullYear();
      var hh = (d.getHours() < 10 ? "0" : "") + d.getHours();
      var mi = (d.getMinutes() < 10 ? "0" : "") + d.getMinutes();
      return dd + " " + mm + " " + yy + " " + hh + ":" + mi;
    } catch (e) { return String(iso); }
  }
  function renderConfidenceMeter(value) {
    var n = (value === null || value === undefined || isNaN(Number(value))) ? 0 : Number(value);
    var pct = n > 1 ? Math.max(0, Math.min(100, n)) : Math.max(0, Math.min(100, n * 100));
    var color = pct >= 70 ? "var(--accent)"
              : pct >= 40 ? "var(--warn)"
              : "var(--danger)";
    return ""
      + '<div class="confidence-meter" title="' + pct.toFixed(0) + '%" '
      + 'role="meter" aria-valuenow="' + pct.toFixed(0) + '" '
      + 'aria-valuemin="0" aria-valuemax="100" '
      + 'aria-label="confidence ' + pct.toFixed(0) + ' percent">'
      +   '<div class="bar" style="height:' + pct.toFixed(0) + '%; --confidence-color:' + color + '"></div>'
      +   '<span class="value">' + pct.toFixed(0) + '%</span>'
      + '</div>';
  }
  function renderActionBadge(action) {
    var raw = (action === null || action === undefined) ? "" : String(action);
    var lower = raw.toLowerCase();
    var cls = lower === "insufficient_evidence" ? "insufficient" : lower;
    return '<span class="badge action-' + escapeHtml(cls) + '">' + escapeHtml(raw || "—") + '</span>';
  }
  function renderComplianceBadge(status) {
    var raw = (status === null || status === undefined) ? "" : String(status);
    var lower = raw.toLowerCase();
    var cls = (lower === "approved" || lower === "review" || lower === "flagged"
            || lower === "blocked"  || lower === "pending")
      ? lower : "unknown";
    return '<span class="badge compliance-' + cls + '">' + escapeHtml(raw || "—") + '</span>';
  }
  function renderEvidenceCard(evidence) {
    if (!evidence || typeof evidence !== "object") {
      return '<article class="evidence-card empty"><div class="evidence-body">—</div></article>';
    }
    var stream   = evidence.stream || evidence.source || "evidence";
    var signal   = (evidence.signal || "NEUTRAL").toString().toUpperCase();
    var strength = Number(evidence.strength);
    var conf     = Number(evidence.confidence);
    var sourceId = evidence.source_id || evidence.sourceId || "—";
    var retrieved= evidence.retrieved_at || evidence.retrievedAt || null;
    var meta     = evidence.metadata || {};
    var dirCls = signal === "BULLISH" ? "pos"
               : signal === "BEARISH" ? "neg"
               : "neutral";
    var metaHtml = "";
    if (meta && typeof meta === "object" && !Array.isArray(meta)) {
      var keys = Object.keys(meta);
      if (keys.length) {
        metaHtml = '<dl class="evidence-meta">'
          + keys.map(function (k) {
              var v = meta[k];
              if (v === null || v === undefined) v = "—";
              if (typeof v === "object") v = JSON.stringify(v);
              return "<dt>" + escapeHtml(k) + "</dt><dd>" + escapeHtml(String(v)) + "</dd>";
            }).join("")
          + "</dl>";
      }
    }
    return ""
      + '<article class="evidence-card">'
      +   "<details>"
      +     "<summary>"
      +       '<span class="evidence-stream">' + escapeHtml(stream) + "</span>"
      +       '<span class="evidence-signal ' + dirCls + '">' + escapeHtml(signal) + "</span>"
      +       '<span class="evidence-strength-label">güç / strength</span>'
      +       renderConfidenceMeter(isNaN(strength) ? 0 : strength)
      +       '<span class="evidence-confidence-label">güvenilirlik / confidence</span>'
      +       renderConfidenceMeter(isNaN(conf) ? 0 : conf)
      +     "</summary>"
      +     '<div class="evidence-body">'
      +       '<p class="evidence-source"><span>Kaynak / Source</span> <code>' + escapeHtml(sourceId) + "</code></p>"
      +       (retrieved ? '<p class="evidence-retrieved"><span>Alınma zamanı / Retrieved at</span> '
      +         + escapeHtml(renderTRT(retrieved)) + "</p>" : "")
      +       metaHtml
      +     "</div>"
      +   "</details>"
      + "</article>";
  }
  function renderTable(headers, rows) {
    var head = "<thead><tr>"
      + headers.map(function (h) {
          return "<th" + (h && h.cls ? ' class="' + escapeHtml(h.cls) + '"' : "") + ">"
               + escapeHtml(h && h.label ? h.label : "") + "</th>";
        }).join("")
      + "</tr></thead>";
    var body;
    if (!rows || rows.length === 0) {
      body = '<tbody><tr><td class="empty-state" colspan="' + headers.length + '">'
           + "Henüz kayıt yok / No records yet"
           + "</td></tr></tbody>";
    } else {
      body = "<tbody>" + rows.map(function (r) {
        return "<tr>" + r.map(function (cell) { return "<td>" + cell + "</td>"; }).join("") + "</tr>";
      }).join("") + "</tbody>";
    }
    return '<div class="table-wrap"><table class="data-table">' + head + body + "</div>";
  }

  Object.assign(window.FA, {
    esc: escapeHtml,
    fmtNum: fmtNum, fmtVol: fmtVol, fmtTime: fmtTime, fmtTRY: fmtTRY, fmtPct: fmtPct,
    normalizeList: normalizeList, parseJsonb: parseJsonb,
    shortId: shortId, detailUrl: detailUrl, decisionsUrl: decisionsUrl,
    renderTRT: renderTRT,
    renderConfidenceMeter: renderConfidenceMeter,
    renderActionBadge: renderActionBadge,
    renderComplianceBadge: renderComplianceBadge,
    renderEvidenceCard: renderEvidenceCard,
    renderTable: renderTable,
  });

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
