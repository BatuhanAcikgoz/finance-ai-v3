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
 * All /api/v1/admin/* calls go through window.FA.api.fetchAdmin() which adds
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
    var url = path;
    return window.FA.api.fetchAdmin(url, { headers: { 'Accept': 'application/json' } })
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
    // FastAPI default route is "" which 307-redirects to "/". That's a
    // network round-trip per call. Append "/" proactively to skip it.
    var url = path;
    if (!/\?/.test(url) && !url.endsWith('/')) url += '/';
    return window.FA.api.fetchAdmin(url, {
      method: method,
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
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
            +     '<button class="btn" data-action="edit"   type="button">Düzenle</button>'
            +     '<button class="btn" data-action="test"   type="button">Test</button>'
            +     '<button class="btn" data-action="delete" type="button">Sil</button>'
            +   '</div>'
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
    var rowIdx = row.getAttribute('data-idx');
    // Toggle: if an edit bar already exists for this row, remove it.
    var existing = row.parentNode.querySelector('[data-edit-apikey-row="' + rowIdx + '"]');
    if (existing) { existing.remove(); return; }

    var bar = document.createElement('div');
    bar.className = 'llm-key-edit-bar';
    bar.setAttribute('data-edit-apikey-row', String(rowIdx));
    bar.innerHTML =
      '<span class="bar-text">' +
        '<strong>' + esc(v.provider) + '/' + esc(v.model) + '</strong> için yeni API anahtarı gir / ' +
        'enter a new API key. Boş bırakırsan değişmez / Leave blank to keep current.' +
      '</span>' +
      '<span class="bar-fields">' +
        '<input type="password" data-apikey-input placeholder="sk-…" autocomplete="off" />' +
        '<button type="button" class="btn btn-show" data-show aria-label="Göster">👁</button>' +
        '<button type="button" class="btn" data-no>İptal / Cancel</button>' +
        '<button type="button" class="btn btn-primary" data-save>Kaydet / Save</button>' +
      '</span>';

    var inp = bar.querySelector('[data-apikey-input]');
    var show = bar.querySelector('[data-show]');
    var no = bar.querySelector('[data-no]');
    var save = bar.querySelector('[data-save]');
    no.addEventListener('click', function () { bar.remove(); });
    save.addEventListener('click', function () {
      var body = Object.assign({}, v, inp.value ? { api_key: inp.value } : {});
      save.disabled = true;
      adminSend('PUT', 'llm/keys', body).then(function (res) {
        if (!res.ok) {
          window.FA.toast.show('Kayıt başarısız / Save failed (' + res.status + ')', 'error');
          save.disabled = false;
          return;
        }
        window.FA.toast.show('Anahtar güncellendi / Key updated');
        bar.remove();
        loadKeys();
      }).catch(function () {
        window.FA.toast.show('Ağ hatası / Network error', 'error');
        save.disabled = false;
      });
    });
    show.addEventListener('click', function () {
      if (inp.type === 'password') { inp.type = 'text'; show.textContent = '🙈'; }
      else                          { inp.type = 'password'; show.textContent = '👁'; }
    });
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); save.click(); }
      if (e.key === 'Escape') { e.preventDefault(); bar.remove(); }
    });
    if (row.nextSibling) row.parentNode.insertBefore(bar, row.nextSibling);
    else row.parentNode.appendChild(bar);
    setTimeout(function () { inp.focus(); }, 30);
  }

  function testKey(row) {
    var v = readKeyFromRow(row);
    window.FA.toast.show('Test ediliyor… / Testing ' + v.provider + '/' + v.model);
    adminSend('POST', 'llm/keys/test', v)
      .then(function (res) {
        if (res.status === 404) { window.FA.toast.show('Test endpoint yok / Not implemented'); return; }
        if (!res.ok) { window.FA.toast.show('Test başarısız / Test failed (' + res.status + ')'); return; }
        window.FA.toast.show('Test başarılı ✓ / Test passed');
      })
      .catch(function () { window.FA.toast.show('Ağ hatası / Network error'); });
  }

  function deleteKey(row) {
      var v = readKeyFromRow(row);
      // Inline confirmation — replaces window.confirm() which browsers
      // commonly disable and which can't be styled. We render the bar in
      // its own grid row beneath the data row so the existing actions cell
      // is replaced (not stacked).
      var existing = row.parentNode.querySelector('[data-delete-confirm-row="' + row.getAttribute('data-idx') + '"]');
      if (existing) { existing.remove(); return; }

      var bar = document.createElement('div');
      bar.className = 'llm-key-delete-bar';
      bar.setAttribute('data-delete-confirm-row', String(row.getAttribute('data-idx')));
      bar.innerHTML =
        '<span class="bar-text">' +
          '<strong>' + esc(v.provider) + '/' + esc(v.model) + '</strong> ' +
          'silinsin mi?  <em>Bu işlem geri alınamaz / This cannot be undone.</em>' +
        '</span>' +
        '<span class="bar-actions">' +
          '<button type="button" class="btn" data-no>İptal / Cancel</button>' +
          '<button type="button" class="btn btn-danger" data-yes>' +
            '<span aria-hidden="true">⚠</span> Sil / Delete' +
          '</button>' +
        '</span>';
      bar.querySelector('[data-no]').addEventListener('click', function () {
        bar.remove();
      });
      bar.querySelector('[data-yes]').addEventListener('click', function () {
        bar.remove();
        adminSend('DELETE', 'llm/keys', { provider: v.provider, model: v.model })
          .then(function (res) {
            if (!res.ok) {
              window.FA.toast.show('Silme başarısız / Delete failed (' + res.status + ')', 'error');
              return;
            }
            window.FA.toast.show('Anahtar silindi / Key deleted');
            loadKeys();
          })
          .catch(function () {
            window.FA.toast.show('Ağ hatası / Network error', 'error');
          });
      });
      // Insert below the row, spanning the whole table width.
      if (row.nextSibling) row.parentNode.insertBefore(bar, row.nextSibling);
      else row.parentNode.appendChild(bar);
    }

  function bindKeysControls() {
    var $refresh = $('#keys-refresh');
    var $add     = $('#keys-add');
    if ($refresh) $refresh.addEventListener('click', loadKeys);

    if ($add) $add.addEventListener('click', function () { openKeyModal(); });
    bindKeyModal();
  }

  // -------- KEY MODAL -------------------------------------------------------
  function openKeyModal() {
    var dlg = document.getElementById('key-modal');
    if (!dlg) {
      console.error('key-modal dialog missing');
      return;
    }
    // Reset form each time so previous inputs don't linger.
    var form = document.getElementById('key-form');
    if (form) form.reset();
    var title = document.getElementById('key-modal-title');
    if (title) title.textContent = 'LLM Anahtarı Ekle / Add LLM Key';
    var submit = document.getElementById('key-form-submit');
    if (submit) submit.disabled = false;

    // Prefill provider/model from current setting so the user lands on the
    // platform default rather than blank.
    fetchJsonSafe('/api/v1/settings/').then(function (s) {
      if (!s || !s.llm) return;
      var pSel = document.getElementById('key-form-provider');
      var mInp = document.getElementById('key-form-model');
      if (pSel && s.llm.provider) pSel.value = s.llm.provider;
      if (mInp && s.llm.model)    mInp.value = s.llm.model;
    });

    if (typeof dlg.showModal === 'function') {
      dlg.showModal();
    } else {
      // Fallback for browsers without <dialog>: render as fixed overlay.
      dlg.setAttribute('open', '');
      dlg.style.position = 'fixed';
      dlg.style.inset = '50% auto auto 50%';
      dlg.style.transform = 'translate(-50%, -50%)';
      dlg.style.zIndex = 1000;
    }
    setTimeout(function () {
      var f = document.getElementById('key-form-provider');
      if (f) f.focus();
    }, 30);
  }

  function closeKeyModal() {
    var dlg = document.getElementById('key-modal');
    if (!dlg) return;
    if (typeof dlg.close === 'function') {
      dlg.close();
    } else {
      dlg.removeAttribute('open');
      dlg.style.position = '';
    }
  }

  function bindKeyModal() {
    var dlg = document.getElementById('key-modal');
    var form = document.getElementById('key-form');
    var close = document.getElementById('key-modal-close');
    var cancel = document.getElementById('key-modal-cancel');
    var showBtn = document.getElementById('key-form-show');
    var apikey = document.getElementById('key-form-apikey');
    if (!dlg || !form) return;

    if (close) close.addEventListener('click', closeKeyModal);
    if (cancel) cancel.addEventListener('click', closeKeyModal);
    // Click outside (on backdrop) closes the dialog.
    dlg.addEventListener('click', function (e) {
      if (e.target === dlg) closeKeyModal();
    });
    // ESC closes dialog natively for <dialog>; ensure cancel button isn't
    // skipped in keyboard nav.
    if (showBtn && apikey) {
      showBtn.addEventListener('click', function () {
        if (apikey.type === 'password') {
          apikey.type = 'text';
          showBtn.setAttribute('aria-label', 'Anahtarı gizle');
          showBtn.textContent = '🙈';
        } else {
          apikey.type = 'password';
          showBtn.setAttribute('aria-label', 'Anahtarı göster');
          showBtn.textContent = '👁';
        }
      });
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var fd = new FormData(form);
      var payload = {
        provider: String(fd.get('provider') || '').trim(),
        model:    String(fd.get('model') || '').trim(),
        label:    String(fd.get('label') || '').trim() || null,
        api_key:  String(fd.get('api_key') || '').trim(),
        set_active: !!document.getElementById('key-form-set-active').checked,
      };
      if (!payload.provider || !payload.model || !payload.api_key) {
        window.FA.toast.show('Sağlayıcı, model ve anahtar zorunlu / Provider, model and key are required', 'error');
        return;
      }
      var submit = document.getElementById('key-form-submit');
      if (submit) submit.disabled = true;
      adminSend('POST', 'llm/keys', payload).then(function (res) {
        if (!res.ok) {
          window.FA.toast.show('Ekleme başarısız / Add failed (' + res.status + ')', 'error');
          if (submit) submit.disabled = false;
          return;
        }
        window.FA.toast.show('Anahtar eklendi / Key added');
        closeKeyModal();
        loadKeys();
      }).catch(function () {
        window.FA.toast.show('Ağ hatası / Network error', 'error');
        var submit2 = document.getElementById('key-form-submit');
        if (submit2) submit2.disabled = false;
      });
    });
  }

  // fetchJsonSafe: GET a URL and parse JSON, never throw. Tiny helper so
  // the prefill-from-current-settings call can't crash the modal flow.
  function fetchJsonSafe(url) {
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
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
    adminGet('audit-log').then(function (data) {
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
    bindKeysControls();
    bindRefreshButtons();
    refreshAll();
    var _refreshTimer = setInterval(refreshAll, REFRESH_MS);
    window.addEventListener('pagehide', function () { clearInterval(_refreshTimer); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();