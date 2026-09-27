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

  // -------- PROVIDER DROPDOWN -------------------------------------------
  // Models are provider-specific, so we rebuild the <datalist> every time
  // the user picks a new provider. The model <input> stays a free-text
  // input backed by that <datalist> — user can still type any custom
  // model string (e.g. a private deployment of MiniMax-m3 behind a
  // corporate proxy).
  var KNOWN_PROVIDERS = []; // populated by GET /v1/settings
  var currentProvider = null;
  function rebuildProviderDropdown(select, providers, selectedId) {
    select.innerHTML = '';
    // Group: official (marked via api_format === "openai" / built-ins) on
    // top, others below. With only ~7 entries there's no real need for
    // <optgroup>s; a flat list with separators keeps the search simple.
    providers.forEach(function (p) {
      var opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label + '  ·  ' + (p.api_format || 'openai');
      opt.dataset.apiFormat = p.api_format || 'openai';
      opt.dataset.baseUrl    = p.base_url || '';
      opt.dataset.models     = (p.models || []).join(',');
      opt.dataset.defaultModel = p.default_model || '';
      opt.dataset.notes      = p.notes || '';
      select.appendChild(opt);
    });
    if (selectedId) {
      select.value = selectedId;
    }
    currentProvider = select.value || null;
  }
  function rebuildModelDatalist(datalist, providerId) {
    datalist.innerHTML = '';
    var provider = KNOWN_PROVIDERS.find(function (p) { return p.id === providerId; });
    if (!provider || !provider.models) return;
    provider.models.forEach(function (m) {
      var opt = document.createElement('option');
      opt.value = m;
      datalist.appendChild(opt);
    });
    // Mirror provider notes in the helper text so the user knows what
    // they're picking.
    var hint = document.getElementById('set-provider-hint');
    if (hint && provider.notes) {
      hint.textContent = provider.notes +
        (provider.base_url ? '  ·  base: ' + provider.base_url : '');
    } else if (hint) {
      hint.textContent = 'Seçilebilir — listeden bir sağlayıcı seçin.';
    }
  }
  function syncApiFormat(select, providerId) {
    var provider = KNOWN_PROVIDERS.find(function (p) { return p.id === providerId; });
    if (!provider) return;
    var apiFmt = document.getElementById('set-api-format');
    if (!apiFmt) return;
    if (Array.from(apiFmt.options).some(function (o) { return o.value === (provider.api_format || 'openai'); })) {
      apiFmt.value = provider.api_format || 'openai';
    }
  }
  function onProviderChange() {
    var sel = document.getElementById('set-provider');
    var datalist = document.getElementById('set-model-list');
    var modelInput = document.getElementById('set-model');
    if (!sel) return;
    currentProvider = sel.value;
    rebuildModelDatalist(datalist, currentProvider);
    syncApiFormat(null, currentProvider);
    // Auto-fill the model's default value when the field is empty or
    // still shows the OLD provider's default. This avoids leaving
    // provider=minimax + model=gpt-4o after a quick provider swap.
    var provider = KNOWN_PROVIDERS.find(function (p) { return p.id === currentProvider; });
    if (provider && modelInput) {
      var knownModels = (provider.models || []).map(function (m) { return m.toLowerCase(); });
      var currentModel = (modelInput.value || '').toLowerCase();
      if (!modelInput.value || knownModels.indexOf(currentModel) === -1) {
        modelInput.value = provider.default_model || (provider.models || [])[0] || '';
      }
    }
  }

  function populateForm(data) {
    if (!data || typeof data !== 'object') return;
    var form = $('#settings-form');
    if (!form) return;

    // First, the provider registry (used by the dropdown + datalist).
    if (Array.isArray(data.providers)) {
      KNOWN_PROVIDERS = data.providers;
      var sel = form.querySelector('#set-provider');
      if (sel) rebuildProviderDropdown(sel, data.providers, (data.llm && data.llm.provider) || '');
    }

    if (data.llm) {
      var provSel = form.querySelector('#set-provider');
      if (provSel) provSel.value = (data.llm.provider || provSel.value || '');
      currentProvider = provSel.value || null;

      // Fill model + datalist for the active provider.
      var datalist = form.querySelector('#set-model-list');
      if (datalist) rebuildModelDatalist(datalist, currentProvider);
      if (data.llm.model) form.querySelector('#set-model').value = data.llm.model;

      // api_format: only set if the saved value is one we know; otherwise
      // let syncApiFormat() pick from the current provider.
      var apiFmt = form.querySelector('#set-api-format');
      if (apiFmt) {
        var savedFmt = data.llm.api_format ||
          (KNOWN_PROVIDERS.find(function (p) { return p.id === currentProvider; }) || {}).api_format ||
          'openai';
        if (Array.from(apiFmt.options).some(function (o) { return o.value === savedFmt; })) {
          apiFmt.value = savedFmt;
        }
      }

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

    // Provider change → refresh the model <datalist> + sync the API format.
    var provSel = form.querySelector('#set-provider');
    if (provSel) {
      provSel.addEventListener('change', onProviderChange);
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var payload = readFormIntoObject();

      // The form has llm.api_format as a sibling <select>, but readFormIntoObject
      // only handles dotted names. Add it explicitly so PATCH round-trips it.
      var apiFmtEl = form.querySelector('#set-api-format');
      if (apiFmtEl && apiFmtEl.value && (!payload.llm || Object.keys(payload.llm).length)) {
        payload.llm = payload.llm || {};
        payload.llm.api_format = apiFmtEl.value;
      }
      // Same treatment for provider / model in case the user touched them.
      if (provSel && provSel.value && (!payload.llm || Object.keys(payload.llm).length)) {
        payload.llm = payload.llm || {};
        payload.llm.provider = provSel.value;
      }
      var modelEl = form.querySelector('#set-model');
      if (modelEl && modelEl.value && (!payload.llm || Object.keys(payload.llm).length)) {
        payload.llm = payload.llm || {};
        payload.llm.model = modelEl.value;
      }

      var $raw = $('#settings-raw');
      if ($raw) $raw.textContent = 'Kaydediliyor… / Saving…';

      saveSettings(payload).then(function (r) {
        if (r.ok) {
          window.FA.ui.toast('Kaydedildi / Saved');
          if ($raw) $raw.textContent = JSON.stringify(r.body, null, 2);
          populateForm(r.body || {});
        } else if (r.status === 400 && r.body && r.body.error === 'unknown_provider') {
          window.FA.ui.toast('Bilinmeyen sağlayıcı / Unknown provider', { type: 'error' });
          if ($raw) $raw.textContent = 'HTTP 400 — ' + (r.body.detail || JSON.stringify(r.body));
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