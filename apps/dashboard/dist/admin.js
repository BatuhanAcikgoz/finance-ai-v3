/* ============================================================================
 * Admin page — vanilla JS, no build step.
 *
 * Sections (each is independently re-renderable):
 *   1) Admin token bar — set/clear X-Admin-Token in localStorage.
 *   2) LLM Keys table  — provider / model / masked_key / last_used / cost / status.
 *   3) LLM Providers   — cards with latency / cost / error rate.
 *   4) System          — CPU / mem / disk / containers / queue.
 *   5) Audit log       — vertical timeline.
 *
 * All /api/v1/admin/* calls go through window.FA.ui.fetchAdmin() which adds
 * the X-Admin-Token header automatically. When the endpoint isn't implemented
 * yet on api-gateway (this is being built in parallel) we degrade gracefully
 * and render an empty-state with a hint.
 * =========================================================================== */
(function () {
  'use strict';

  var REFRESH_MS = 30000;

  var PROVIDERS = ['openai', 'anthropic', 'gemini', 'mistral', 'ollama', 'deepseek'];
  var STATUSES  = ['active', 'inactive', 'error'];

  // -------- Tiny helpers ---------------------------------------------------
  function $(sel) { return document.querySelector(sel); }
  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function maskKey(k) {
    if (!k) return '—';
    if (k.length <= 8) return '••••';
    return k.slice(0, 4) + '••••' + k.slice(-4);
  }
  function fmtTime(d) {
    if (!d) return '—';
    try {
      var dt = (d instanceof Date) ? d : new Date(d);
      if (isNaN(dt.getTime())) return '—';
      return dt.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
    } catch (e) { return '—'; }
  }
  function fmtUSD(n) {
    if (n === null || n === undefined || isNaN(Number(n))) return '—';
    return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function statusClass(s) {
    if (s === 'active')   return 'is-active';
    if (s === 'inactive') return 'is-inactive';
    return 'is-error';
  }
  function statusLabel(s) {
    if (s === 'active')   return 'Aktif / Active';
    if (s === 'inactive') return 'Pasif / Inactive';
    if (s === 'error')    return 'Hata / Error';
    return s || '—';
  }

  /**
   * GET /api/v1/admin/<path>. Returns parsed JSON, or null on 404 (endpoint
   * not implemented yet — caller should show "no data" rather than error).
   * On 401/403 we surface a clear "token invalid" hint.
   */
  function adminGet(path) {
    var url = '/api/v1/admin/' + path;
    return window.FA.ui.fetchAdmin(url, { headers: { 'Accept': 'application/json' } })
      .then(function (res) {
        if (res.status === 404) return null;
        if (res.status === 401 || res.status === 403) {
          return { __denied: true, status: res.status };
        }
        if (!res.ok) return Promise.reject(new Error('HTTP ' + res.status));
        return res.json();
      })
      .catch(function () { return null; });
  }

  function adminSend(method, path, body) {
    var url = '/api/v1/admin/' + path;
    return window.FA.ui.fetchAdmin(url, {
      method: method,
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  // -------- Token bar ------------------------------------------------------
  function bindTokenBar() {
    var $input = $('#admin-token');
    var $save  = $('#admin-token-save');
    var $clear = $('#admin-token-clear');
    var $test  = $('#admin-test');

    if ($input) $input.value = window.FA.ui.getAdminToken();

    if ($save) $save.addEventListener('click', function () {
      window.FA.ui.setAdminToken($input.value || '');
      window.FA.ui.toast('Token kaydedildi / Saved');
    });
    if ($clear) $clear.addEventListener('click', function () {
      $input.value = '';
      window.FA.ui.setAdminToken('');
      window.FA.ui.toast('Token silindi / Cleared');
    });
    if ($test) $test.addEventListener('click', function () {
      // Quick read of /api/v1/admin/llm/keys — 200 or 401/403 is informative.
      window.FA.ui.fetchAdmin('/api/v1/admin/llm/keys', { headers: { 'Accept': 'application/json' } })
        .then(function (res) {
          if (res.status === 404) { window.FA.ui.toast('Endpoint henüz yok / Not implemented (404)'); return; }
          if (res.status === 401 || res.status === 403) { window.FA.ui.toast('Token geçersiz / Token rejected (' + res.status + ')'); return; }
          if (res.ok) { window.FA.ui.toast('Bağlantı başarılı / Connected ✓'); return; }
          window.FA.ui.toast('Beklenmeyen yanıt / Unexpected (' + res.status + ')');
        })
        .catch(function () { window.FA.ui.toast('Ağ hatası / Network error'); });
    });
  }

  // -------- LLM KEYS -------------------------------------------------------
  function renderKeysRow(k, idx) {
    var last = fmtTime(k.last_used);
    var cost = fmtUSD(k.cost_usd);
    return ''
      + '<div class="llm-key-row" data-idx="' + idx + '">'
      +   '<div><select data-field="provider">'
      +     PROVIDERS.map(function (p) {
            return '<option value="' + p + '"' + (p === k.provider ? ' selected' : '') + '>' + esc(p) + '</option>';
          }).join('')
      +   '</select></div>'
      +   '<div><input type="text" data-field="model" value="' + esc(k.model || '') + '" placeholder="örn. gpt-4o" /></div>'
      +   '<div class="key-mask">' + esc(maskKey(k.api_key)) + '</div>'
      +   '<div>' + esc(last) + '</div>'
      +   '<div><span class="status-dot ' + statusClass(k.status) + '" aria-hidden="true"></span> '
      +     esc(statusLabel(k.status)) + '</div>'
      +   '<div>' + esc(cost) + '</div>'
      +   '<div class="actions">'
      +     '<button class="btn" data-action="edit"   type="button">Düzenle / Edit</button>'
      +     '<button class="btn" data-action="test"   type="button">Test</button>'
      +     '<button class="btn" data-action="delete" type="button">Sil / Delete</button>'
      +   '</div>'
      +   '<div></div>'
      + '</div>';
  }

  function loadKeys() {
    var $body = $('#llm-keys-body');
    if (!$body) return;
    $body.innerHTML = '<div class="llm-key-row empty-state" style="grid-column: 1 / -1;">Yükleniyor… / Loading…</div>';

    adminGet('llm/keys').then(function (data) {
      if (data && data.__denied) {
        $body.innerHTML = '<div class="llm-key-row empty-state" style="grid-column: 1 / -1;">'
          + 'Erişim reddedildi (HTTP ' + data.status + '). Admin token gerekiyor. / Access denied — admin token required.'
          + '</div>';
        return;
      }
      if (!data) {
        $body.innerHTML = '<div class="llm-key-row empty-state" style="grid-column: 1 / -1;">'
          + 'Endpoint henüz implemente edilmedi (404) veya veri yok. / Endpoint not yet implemented.'
          + '</div>';
        return;
      }
      var list = Array.isArray(data) ? data : (data.items || data.keys || []);
      if (!list.length) {
        $body.innerHTML = '<div class="llm-key-row empty-state" style="grid-column: 1 / -1;">'
          + 'Henüz anahtar yok. / No keys yet.'
          + '</div>';
        return;
      }
      $body.innerHTML = list.map(renderKeysRow).join('');
      $body.querySelectorAll('[data-action]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var row = btn.closest('.llm-key-row');
          var action = btn.dataset.action;
          if (action === 'edit') return editKey(row);
          if (action === 'test') return testKey(row);
          if (action === 'delete') return deleteKey(row);
        });
      });
    });
  }

  function readKeyFromRow(row) {
    return {
      provider: (row.querySelector('[data-field="provider"]')).value,
      model:    (row.querySelector('[data-field="model"]')).value,
    };
  }

  function editKey(row) {
    var v = readKeyFromRow(row);
    var newApiKey = window.prompt('Yeni API anahtarı / New API key (boş = değiştirme):', '');
    if (newApiKey === null) return;
    adminSend('PUT', 'llm/keys', Object.assign({}, v, newApiKey ? { api_key: newApiKey } : {}))
      .then(function (res) {
        if (!res.ok) { window.FA.ui.toast('Kayıt başarısız / Save failed (' + res.status + ')'); return; }
        window.FA.ui.toast('Anahtar güncellendi / Key updated');
        loadKeys();
      })
      .catch(function () { window.FA.ui.toast('Ağ hatası / Network error'); });
  }

  function testKey(row) {
    var v = readKeyFromRow(row);
    window.FA.ui.toast('Test ediliyor… / Testing ' + v.provider + '/' + v.model);
    adminSend('POST', 'llm/keys/test', v)
      .then(function (res) {
        if (res.status === 404) { window.FA.ui.toast('Test endpoint yok / Not implemented'); return; }
        if (!res.ok) { window.FA.ui.toast('Test başarısız / Test failed (' + res.status + ')'); return; }
        window.FA.ui.toast('Test başarılı ✓ / Test passed');
      })
      .catch(function () { window.FA.ui.toast('Ağ hatası / Network error'); });
  }

  function deleteKey(row) {
    var v = readKeyFromRow(row);
    if (!window.confirm('Silmek istediğinize emin misiniz? / Delete ' + v.provider + '/' + v.model + '?')) return;
    adminSend('DELETE', 'llm/keys', v)
      .then(function (res) {
        if (!res.ok) { window.FA.ui.toast('Silme başarısız / Delete failed (' + res.status + ')'); return; }
        window.FA.ui.toast('Anahtar silindi / Key deleted');
        loadKeys();
      })
      .catch(function () { window.FA.ui.toast('Ağ hatası / Network error'); });
  }

  function bindKeysControls() {
    var $refresh = $('#keys-refresh');
    var $add     = $('#keys-add');
    if ($refresh) $refresh.addEventListener('click', loadKeys);
    if ($add) $add.addEventListener('click', function () {
      var provider = window.prompt('Sağlayıcı / Provider (openai / anthropic / gemini / …):', 'openai');
      if (!provider) return;
      var model = window.prompt('Model (örn. gpt-4o):', 'gpt-4o');
      if (!model) return;
      var api_key = window.prompt('API anahtarı / API key:', '');
      if (!api_key) { window.FA.ui.toast('İptal / Cancelled'); return; }
      adminSend('POST', 'llm/keys', { provider: provider, model: model, api_key: api_key })
        .then(function (res) {
          if (!res.ok) { window.FA.ui.toast('Ekleme başarısız / Add failed (' + res.status + ')'); return; }
          window.FA.ui.toast('Anahtar eklendi / Key added');
          loadKeys();
        })
        .catch(function () { window.FA.ui.toast('Ağ hatası / Network error'); });
    });
  }

  // -------- PROVIDERS ------------------------------------------------------
  function renderProviderCard(p) {
    return ''
      + '<div class="provider-card">'
      +   '<div class="provider-header">'
      +     '<div class="provider-name">' + esc(p.name || p.provider || '—') + '</div>'
      +     '<span class="status-dot ' + statusClass(p.status) + '" aria-hidden="true"></span>'
      +   '</div>'
      +   '<div class="provider-meta">'
      +     '<span>' + esc(p.model || '—') + '</span>'
      +     '<span>· ' + esc(p.region || '—') + '</span>'
      +   '</div>'
      +   '<div class="provider-stats">'
      +     '<div class="provider-stat"><div class="label">Gecikme / Latency (ms)</div><div class="value">' + esc(p.latency_ms != null ? p.latency_ms : '—') + '</div></div>'
      +     '<div class="provider-stat"><div class="label">Bugün / Today (USD)</div><div class="value">' + esc(fmtUSD(p.cost_today_usd)) + '</div></div>'
      +     '<div class="provider-stat"><div class="label">Hata / Errors %</div><div class="value">' + esc(p.error_pct != null ? p.error_pct : '—') + '</div></div>'
      +   '</div>'
      + '</div>';
  }

  function loadProviders() {
    var $grid = $('#providers-grid');
    if (!$grid) return;
    $grid.innerHTML = '<div class="empty-state">Yükleniyor… / Loading…</div>';
    adminGet('llm/providers').then(function (data) {
      if (data && data.__denied) {
        $grid.innerHTML = '<div class="empty-state">Erişim reddedildi / Access denied.</div>';
        return;
      }
      if (!data) {
        $grid.innerHTML = '<div class="empty-state">Endpoint henüz yok / Not implemented yet.</div>';
        return;
      }
      var list = Array.isArray(data) ? data : (data.items || data.providers || []);
      if (!list.length) { $grid.innerHTML = '<div class="empty-state">Henüz sağlayıcı yok / No providers.</div>'; return; }
      $grid.innerHTML = list.map(renderProviderCard).join('');
    });
  }

  // -------- SYSTEM ---------------------------------------------------------
  function renderSysTile(label, value, pct) {
    var cls = '';
    if (typeof pct === 'number') {
      if (pct >= 85) cls = 'danger';
      else if (pct >= 65) cls = 'warn';
    }
    var bar = (typeof pct === 'number')
      ? '<div class="bar"><span class="' + cls + '" style="width:' + pct + '%;"></span></div>'
      : '';
    return ''
      + '<div class="sys-tile">'
      +   '<div class="label">' + esc(label) + '</div>'
      +   '<div class="value">' + esc(value) + '</div>'
      +   bar
      + '</div>';
  }

  function loadSystem() {
    var $grid = $('#sys-grid');
    var $meta = $('#sys-meta');
    if (!$grid) return;
    adminGet('system').then(function (data) {
      if (!data) {
        $grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1;">Endpoint henüz yok / Not implemented.</div>';
        return;
      }
      var cpu  = (data.cpu_pct  != null) ? data.cpu_pct  : null;
      var mem  = (data.mem_pct  != null) ? data.mem_pct  : null;
      var disk = (data.disk_pct != null) ? data.disk_pct : null;
      var containers = data.containers_running;
      var queueDepth = data.queue_depth;
      var llmCost    = data.llm_cost_today_usd;

      $grid.innerHTML = ''
        + renderSysTile('CPU', cpu != null ? cpu.toFixed(1) + '%' : '—', cpu)
        + renderSysTile('Bellek / Memory', mem != null ? mem.toFixed(1) + '%' : '—', mem)
        + renderSysTile('Disk', disk != null ? disk.toFixed(1) + '%' : '—', disk)
        + renderSysTile('Konteyner / Containers', containers != null ? containers : '—')
        + renderSysTile('Kuyruk / Queue', queueDepth != null ? queueDepth : '—')
        + renderSysTile('LLM Maliyet / Cost', fmtUSD(llmCost));

      if ($meta) {
        var t = data.probed_at ? fmtTime(data.probed_at) : '—';
        $meta.textContent = 'Son ölçüm / last probe: ' + t;
      }
    });
  }

  // -------- AUDIT LOG ------------------------------------------------------
  function loadAudit() {
    var $list = $('#audit-list');
    if (!$list) return;
    adminGet('audit').then(function (data) {
      if (!data) {
        $list.innerHTML = '<li class="empty-state" style="padding-left:32px;">Endpoint henüz yok / Not implemented.</li>';
        return;
      }
      var list = Array.isArray(data) ? data : (data.items || data.events || []);
      if (!list.length) {
        $list.innerHTML = '<li class="empty-state" style="padding-left:32px;">Henüz olay yok / No events yet.</li>';
        return;
      }
      $list.innerHTML = list.map(function (ev) {
        return ''
          + '<li>'
          +   '<span class="ts">'  + esc(fmtTime(ev.ts || ev.timestamp)) + '</span>'
          +   '<span class="src">' + esc(ev.source || ev.actor || '—') + '</span>'
          +   '<span>' + esc(ev.message || ev.action || JSON.stringify(ev)) + '</span>'
          + '</li>';
      }).join('');
    });
  }

  // -------- Boot ----------------------------------------------------------
  function refreshAll() {
    loadKeys();
    loadProviders();
    loadSystem();
    loadAudit();
  }

  function bindRefreshButtons() {
    var $r = $('#providers-refresh'); if ($r) $r.addEventListener('click', loadProviders);
    var $a = $('#audit-refresh');     if ($a) $a.addEventListener('click', loadAudit);
  }

  function boot() {
    bindTokenBar();
    bindKeysControls();
    bindRefreshButtons();
    refreshAll();
    setInterval(refreshAll, REFRESH_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();