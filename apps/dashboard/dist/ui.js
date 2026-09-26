/* ============================================================================
 * ui.js — minimal UI surface used by every page (issue: app.js was overview-
 * specific and threw on missing DOM elements when loaded by admin.html etc.,
 * taking window.FA.ui down with it). Defines only the helpers that are
 * actually safe cross-page: theme, toast, admin-token, fetchAdmin.
 *
 * The big overview-only app.js keeps the heavy lifting (symbols table, charts,
 * WebSocket live tick) on the index page only.
 * ============================================================================ */
(function () {
  'use strict';

  // ---- Theme ---------------------------------------------------------------
  var THEME_KEY = 'finance-ai.theme';
  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }
  function toggleTheme() {
    var next = getTheme() === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
    return next;
  }

  // ---- Admin token + fetchAdmin -------------------------------------------
  var ADMIN_TOKEN_KEY = 'finance-ai.admin_token';
  function getAdminToken() {
    try { return localStorage.getItem(ADMIN_TOKEN_KEY) || ''; }
    catch (e) { return ''; }
  }
  function setAdminToken(v) {
    try {
      if (v) localStorage.setItem(ADMIN_TOKEN_KEY, v);
      else   localStorage.removeItem(ADMIN_TOKEN_KEY);
    } catch (e) {}
  }
  function fetchAdmin(url, opts) {
    opts = opts || {};
    opts.headers = Object.assign({}, opts.headers || {}, {
      'Accept': 'application/json',
      'X-Admin-Token': getAdminToken(),
    });
    return fetch(url, opts);
  }

  // ---- Toast ---------------------------------------------------------------
  function ensureToastContainer() {
    var el = document.querySelector('.toast-container');
    if (el) return el;
    el = document.createElement('div');
    el.className = 'toast-container';
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
    return el;
  }
  function toast(type, message, opts) {
    type = type || 'info';
    opts = opts || {};
    var container = ensureToastContainer();
    var node = document.createElement('div');
    node.className = 'toast toast-' + type;
    node.setAttribute('role', type === 'error' ? 'alert' : 'status');
    var text = document.createElement('span');
    text.textContent = message;
    node.appendChild(text);
    var progress = document.createElement('span');
    progress.className = 'toast-progress';
    node.appendChild(progress);
    container.appendChild(node);
    var ttl = opts.ttl || 4000;
    var dismiss = function () {
      node.classList.add('toast-dismissing');
      setTimeout(function () { node.remove(); }, 220);
    };
    node.addEventListener('click', dismiss);
    setTimeout(dismiss, ttl);
    return dismiss;
  }

  // ---- Empty state ---------------------------------------------------------
  function emptyState(opts) {
    opts = opts || {};
    var node = document.createElement('div');
    node.className = 'empty-state';
    node.setAttribute('role', 'status');
    if (opts.icon) {
      var ico = document.createElement('span');
      ico.innerHTML = opts.icon;
      node.appendChild(ico);
    }
    var title = document.createElement('div');
    title.className = 'empty-title';
    title.textContent = opts.title || 'Veri yok / Nothing here yet';
    node.appendChild(title);
    if (opts.body) {
      var body = document.createElement('div');
      body.className = 'empty-body';
      body.textContent = opts.body;
      node.appendChild(body);
    }
    if (opts.cta) {
      var btn = document.createElement('button');
      btn.className = 'empty-cta';
      btn.textContent = opts.cta;
      if (opts.onClick) btn.addEventListener('click', opts.onClick);
      node.appendChild(btn);
    }
    return node;
  }

  // ---- Skip-to-main link ---------------------------------------------------
  (function addSkipLink() {
    if (document.querySelector('.skip-link')) return;
    var a = document.createElement('a');
    a.className = 'skip-link';
    a.href = '#main';
    a.textContent = 'İçeriğe atla / Skip to content';
    document.body.insertBefore(a, document.body.firstChild);
  })();

  // ---- Public surface ------------------------------------------------------
  window.FA = window.FA || {};
  window.FA.ui = {
    applyTheme:      applyTheme,
    toggleTheme:     toggleTheme,
    getTheme:        getTheme,
    getAdminToken:   getAdminToken,
    setAdminToken:   setAdminToken,
    fetchAdmin:      fetchAdmin,
    toast:           toast,
    emptyState:      emptyState,
  };

  // ---- Theme toggle button hookup ------------------------------------------
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    e.preventDefault();
    var next = toggleTheme();
    btn.setAttribute('aria-pressed', next === 'dark' ? 'true' : 'false');
    btn.setAttribute('title', next === 'dark'
      ? 'Karanlık mod / Dark mode (tıklayın → aydınlık)'
      : 'Aydınlık mod / Light mode (tıklayın → karanlık)');
  });

  // ---- Keyboard shortcuts (Cmd+K + G + letter) ----------------------------
  var CMD_ACTIONS = [
    { label: 'Genel Bakış / Overview', href: '/', hint: 'G O' },
    { label: 'Kararlar / Decisions', href: '/decisions.html', hint: 'G D' },
    { label: 'Portföy / Portfolio', href: '/portfolio.html', hint: 'G P' },
    { label: 'Uyarılar / Alerts', href: '/alerts.html', hint: 'G A' },
    { label: 'Sistem Sağlığı / System Health', href: '/system-health.html', hint: 'G S' },
    { label: 'Admin', href: '/admin.html', hint: 'G .' },
    { label: 'Ayarlar / Settings', href: '/settings.html', hint: 'G ,' },
  ];
  function openCommandBar() {
    if (document.querySelector('.command-bar')) return;
    var overlay = document.createElement('div');
    overlay.className = 'command-bar';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Komut paleti / Command palette');
    overlay.innerHTML =
      '<div class="cmd-panel">' +
        '<input type="text" placeholder="Bir sayfa veya eylem yazın… / Type a page or action…" aria-label="Search">' +
        '<ul role="listbox"></ul>' +
      '</div>';
    var input = overlay.querySelector('input');
    var list  = overlay.querySelector('ul');
    function render(filter) {
      list.innerHTML = '';
      var f = (filter || '').toLowerCase();
      var matches = CMD_ACTIONS.filter(function (a) {
        return !f || a.label.toLowerCase().indexOf(f) >= 0;
      });
      matches.slice(0, 10).forEach(function (a, i) {
        var li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.setAttribute('data-href', a.href);
        if (i === 0) li.setAttribute('aria-selected', 'true');
        li.innerHTML =
          '<span>' + a.label + '</span>' +
          '<span class="cmd-hint">' + (a.hint || '') + '</span>';
        li.addEventListener('click', function () { window.location.href = a.href; });
        list.appendChild(li);
      });
      if (matches.length === 0) {
        var li = document.createElement('li');
        li.style.color = 'var(--muted)';
        li.style.cursor = 'default';
        li.textContent = 'Eşleşen sonuç yok / No matches';
        list.appendChild(li);
      }
    }
    render('');
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    function close() {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      if (e.key === 'Enter') {
        var sel = list.querySelector('li[aria-selected="true"]');
        if (sel) window.location.href = sel.getAttribute('data-href');
      }
    }
    input.addEventListener('input', function () { render(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        var items = list.querySelectorAll('li[data-href]');
        if (!items.length) return;
        var idx = -1;
        items.forEach(function (it, i) {
          if (it.getAttribute('aria-selected') === 'true') idx = i;
          it.removeAttribute('aria-selected');
        });
        if (e.key === 'ArrowDown') idx = Math.min(items.length - 1, idx + 1);
        else                       idx = Math.max(0, idx - 1);
        items[idx].setAttribute('aria-selected', 'true');
        items[idx].scrollIntoView({ block: 'nearest' });
      }
    });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    setTimeout(function () { input.focus(); }, 10);
  }

  var _gArmed = false;
  var _gArmedAt = 0;
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openCommandBar();
      return;
    }
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) {
      return;
    }
    if (e.key.toLowerCase() === 'g' && !_gArmed) {
      _gArmed = true;
      _gArmedAt = Date.now();
      setTimeout(function () { _gArmed = false; }, 1500);
      return;
    }
    if (_gArmed && Date.now() - _gArmedAt < 1500) {
      var map = {
        'o': '/', 'd': '/decisions.html', 'p': '/portfolio.html',
        'a': '/alerts.html', 's': '/system-health.html',
        ',': '/settings.html', '.': '/admin.html',
      };
      var dest = map[e.key.toLowerCase()];
      if (dest) {
        e.preventDefault();
        _gArmed = false;
        window.location.href = dest;
      }
    }
  });
})();
