/* ============================================================================
 * Settings page — vanilla JS.
 *
 * Two concerns:
 *   1) LOCAL theme picker (System / Light / Dark). Lives in localStorage
 *      ONLY — never sent to the server. Updates <html data-theme> + reloads
 *      the theme-toggle pill in the nav.
 *   2) SERVER settings form: GET /api/v1/settings/ on load, PATCH on submit.
 *      Toast "Kaydedildi / Saved" on success.
 * =========================================================================== */
(function () {
  'use strict';

  var SETTINGS_KEY = 'finance-ai.theme'; // already used by app.js; we only need choice keys

  function $(sel) { return document.querySelector(sel); }
  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // -------- LOCAL THEME PICKER --------------------------------------------
  function bindThemePicker() {
    var picker = $('#theme-picker');
    if (!picker) return;

    function activeChoice() {
      var stored;
      try { stored = localStorage.getItem(SETTINGS_KEY); } catch (e) {}
      if (stored === 'light' || stored === 'dark') return stored;
      return 'system';
    }

    function paint() {
      var active = activeChoice();
      picker.querySelectorAll('.theme-card').forEach(function (card) {
        card.classList.toggle('is-active', card.dataset.themeChoice === active);
      });
    }

    picker.addEventListener('click', function (e) {
      var card = e.target.closest('.theme-card');
      if (!card) return;
      var choice = card.dataset.themeChoice;
      try {
        if (choice === 'system') localStorage.removeItem(SETTINGS_KEY);
        else localStorage.setItem(SETTINGS_KEY, choice);
      } catch (err) {}
      window.FA.ui.applyTheme(window.FA.ui.getTheme());
      // Re-evaluate theme against system for "system" choice.
      if (choice === 'system') {
        var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
        var t = (mq && mq.matches) ? 'light' : 'dark';
        window.FA.ui.applyTheme(t);
      }
      paint();
      window.FA.ui.toast('Tema güncellendi / Theme updated');
    });

    paint();
  }

  // -------- SERVER SETTINGS ------------------------------------------------
  function readFormIntoObject() {
    var form = $('#settings-form');
    if (!form) return {};
    var out = {
      llm: {},
      risk: {},
      sources: {},
      notify: {},
    };
    var fd = new FormData(form);
    fd.forEach(function (value, name) {
      if (name.indexOf('.') < 0) return;
      var parts = name.split('.');
      var cur = out;
      for (var i = 0; i < parts.length - 1; i++) {
        cur[parts[i]] = cur[parts[i]] || {};
        cur = cur[parts[i]];
      }
      cur[parts[parts.length - 1]] = value;
    });

    // Coerce numbers and booleans.
    if (out.llm.monthly_budget_usd !== undefined) {
      var n = Number(out.llm.monthly_budget_usd);
      if (!isNaN(n)) out.llm.monthly_budget_usd = n;
      else delete out.llm.monthly_budget_usd;
    }
    if (out.risk.max_position_pct !== undefined) {
      var n2 = Number(out.risk.max_position_pct);
      if (!isNaN(n2)) out.risk.max_position_pct = n2;
      else delete out.risk.max_position_pct;
    }
    if (out.risk.max_sector_pct !== undefined) {
      var n3 = Number(out.risk.max_sector_pct);
      if (!isNaN(n3)) out.risk.max_sector_pct = n3;
      else delete out.risk.max_sector_pct;
    }
    if (out.sources.news !== undefined) {
      out.sources.news = String(out.sources.news || '')
        .split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      if (!out.sources.news.length) delete out.sources.news;
    }
    if (out.notify.email !== undefined) {
      out.notify.email = out.notify.email === 'true' || out.notify.email === true;
    }
    if (out.notify.dashboard !== undefined) {
      out.notify.dashboard = out.notify.dashboard === 'true' || out.notify.dashboard === true;
    }

    // Strip empty leaves.
    Object.keys(out).forEach(function (k) {
      if (out[k] && typeof out[k] === 'object' && !Object.keys(out[k]).length) delete out[k];
    });
    return out;
  }

  function populateForm(data) {
    if (!data || typeof data !== 'object') return;
    var form = $('#settings-form');
    if (!form) return;
    if (data.llm) {
      if (data.llm.provider)              form.querySelector('#set-provider').value = data.llm.provider;
      if (data.llm.model)                 form.querySelector('#set-model').value    = data.llm.model;
      if (data.llm.monthly_budget_usd != null) form.querySelector('#set-budget').value = data.llm.monthly_budget_usd;
    }
    if (data.risk) {
      if (data.risk.max_position_pct != null) form.querySelector('#set-maxpos').value = data.risk.max_position_pct;
      if (data.risk.max_sector_pct  != null) form.querySelector('#set-maxsec').value = data.risk.max_sector_pct;
    }
    if (data.sources && Array.isArray(data.sources.news)) {
      form.querySelector('#set-news').value = data.sources.news.join(', ');
    }
    if (data.notify) {
      if (data.notify.email     != null) form.querySelector('#set-notify-email').value = data.notify.email ? 'true' : 'false';
      if (data.notify.dashboard != null) form.querySelector('#set-notify-dash').value  = data.notify.dashboard ? 'true' : 'false';
    }
    if (data.user) {
      var u = $('#settings-user');
      if (u) u.textContent = 'kullanıcı / user: ' + data.user;
    }
  }

  function loadSettings() {
    var $raw = $('#settings-raw');
    if ($raw) $raw.textContent = 'Yükleniyor… / Loading…';
    return fetch('/api/v1/settings/', { headers: { 'Accept': 'application/json' } })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        populateForm(data);
        if ($raw) $raw.textContent = JSON.stringify(data, null, 2);
      })
      .catch(function (err) {
        if ($raw) $raw.textContent = 'Hata / Error: ' + (err && err.message ? err.message : err);
      });
  }

  function saveSettings(payload) {
    return fetch('/api/v1/settings/', {
      method: 'PATCH',
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(function (res) {
      var ok = res.ok;
      return res.text().then(function (txt) {
        var body; try { body = JSON.parse(txt); } catch (e) { body = txt; }
        return { ok: ok, status: res.status, body: body };
      });
    });
  }

  function bindServerForm() {
    var form = $('#settings-form');
    if (!form) return;
    var $reload = $('#settings-reload');

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var payload = readFormIntoObject();
      var $raw = $('#settings-raw');
      if ($raw) $raw.textContent = 'Kaydediliyor… / Saving…';

      saveSettings(payload).then(function (r) {
        if (r.ok) {
          window.FA.ui.toast('Kaydedildi / Saved');
          if ($raw) $raw.textContent = JSON.stringify(r.body, null, 2);
          populateForm(r.body || {});
        } else {
          window.FA.ui.toast('Hata / Error (' + r.status + ')');
          if ($raw) $raw.textContent = 'HTTP ' + r.status + '\n' + (typeof r.body === 'string' ? r.body : JSON.stringify(r.body, null, 2));
        }
      }).catch(function (err) {
        window.FA.ui.toast('Ağ hatası / Network error');
        if ($raw) $raw.textContent = 'Ağ hatası / Network error: ' + (err && err.message ? err.message : err);
      });
    });

    if ($reload) $reload.addEventListener('click', loadSettings);
  }

  // -------- BOOT ----------------------------------------------------------
  function boot() {
    bindThemePicker();
    bindServerForm();
    loadSettings();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();