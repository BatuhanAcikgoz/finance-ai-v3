/* ============================================================================
 * Decisions list page.
 *   GET /api/v1/decisions/recent?ticker=&compliance_status=&limit=200
 * Filters:
 *   - ticker        (server-side, case-insensitive)
 *   - compliance    (server-side)
 *   - date range    (client-side; server returns at most 200 rows)
 *   - action        (client-side)
 *   - confidence    (client-side)
 * Auto-refreshes every 30s; manual "Refresh" button forces a reload.
 * ============================================================================ */
(function () {
  'use strict';

  // --- DOM refs -------------------------------------------------------------
  var $refresh    = document.getElementById('refresh-indicator');
  var $host       = document.getElementById('results-host');
  var $errBox     = document.getElementById('results-error');
  var $count      = document.getElementById('results-count');
  var $lastUpd    = document.getElementById('last-updated');
  var $datalist   = document.getElementById('ticker-list');

  var $from       = document.getElementById('f-from');
  var $to         = document.getElementById('f-to');
  var $ticker     = document.getElementById('f-ticker');
  var $action     = document.getElementById('f-action');
  var $confidence = document.getElementById('f-confidence');
  var $confRead   = document.getElementById('f-confidence-readout');
  var $compliance = document.getElementById('f-compliance');
  var $clear      = document.getElementById('f-clear');
  var $refreshBtn = document.getElementById('f-refresh');

  // --- State ----------------------------------------------------------------
  var STATE = {
    raw: [],          // last raw list from API
    lastUpdated: 0,
  };

  // --- Helpers --------------------------------------------------------------
  function setLoading(on) {
    if (on) $refresh.classList.add('is-loading');
    else    $refresh.classList.remove('is-loading');
  }

  function fmtPctShort(pct) {
    if (pct === null || pct === undefined || isNaN(Number(pct))) return '—';
    var v = Number(pct);
    var sign = v >= 0 ? '+' : '';
    return sign + v.toFixed(2) + '%';
  }

  function setDefaultDateRange() {
    var now = new Date();
    var week = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    function isoDate(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
    $from.value = isoDate(week);
    $to.value   = isoDate(now);
  }

  function inDateRange(iso, fromStr, toStr) {
    if (!iso) return true;
    if (!fromStr && !toStr) return true;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return true;
    if (fromStr) {
      var f = new Date(fromStr + 'T00:00:00');
      if (d < f) return false;
    }
    if (toStr) {
      var t = new Date(toStr + 'T23:59:59');
      if (d > t) return false;
    }
    return true;
  }

  // --- Render ---------------------------------------------------------------
  function renderError(msg) {
    if (!msg) {
      $errBox.innerHTML = '';
      return;
    }
    $errBox.innerHTML = '<div class="error-state">' + window.FA.esc(msg) + '</div>';
  }

  function renderEmpty(message) {
    var msg = message || 'Henüz karar yok / No decisions yet';
    $host.innerHTML = ''
      + '<div class="empty-state">'
      +   '<p>' + window.FA.esc(msg) + '</p>'
      +   '<p style="margin-top:12px;font-size:11px;color:var(--muted)">'
      +     'Henüz karar motoru verisi gelmemiş olabilir. Birazdan tekrar deneyin.'
      +   '</p>'
      +   '<button type="button" class="btn btn-primary" id="empty-retry" '
      +           'style="margin-top:12px">Tekrar dene / Retry</button>'
      + '</div>';
    var btn = document.getElementById('empty-retry');
    if (btn) btn.addEventListener('click', loadAndRender);
  }

  function renderTable(list) {
    var headers = [
      { label: 'ID' },
      { label: 'Sembol / Ticker' },
      { label: 'Aksiyon / Action' },
      { label: 'Güven / Confidence' },
      { label: 'Poz. Büyüklük / Size', cls: 'num' },
      { label: 'Geçerlilik / Effective At' },
      { label: 'Uyum / Compliance' },
      { label: 'Detay / Detail' },
    ];
    var rows = list.map(function (d) {
      var id = d.decision_id;
      var ticker = d.ticker || '—';
      var size = (d.position_size_pct !== undefined && d.position_size_pct !== null)
        ? (Number(d.position_size_pct) * 100).toFixed(1) + '%'
        : '—';
      var ts = d.effective_at || d.created_at || null;
      return [
        '<code>' + window.FA.esc(window.FA.shortId(id)) + '</code>',
        '<strong>' + window.FA.esc(ticker) + '</strong>',
        window.FA.renderActionBadge(d.action),
        window.FA.renderConfidenceMeter(d.confidence),
        '<span class="num">' + window.FA.esc(size) + '</span>',
        window.FA.esc(window.FA.renderTRT(ts)),
        window.FA.renderComplianceBadge(d.compliance_status),
        '<a href="' + window.FA.esc(window.FA.detailUrl(id)) + '">aç →</a>',
      ];
    });
    $host.innerHTML = window.FA.renderTable(headers, rows);

    // Wire row clicks → detail page.
    var trs = $host.querySelectorAll('table.data-table tbody tr');
    Array.prototype.forEach.call(trs, function (tr, idx) {
      tr.addEventListener('click', function (e) {
        // Let the explicit Detail link do its own thing.
        if (e.target && e.target.tagName === 'A') return;
        var d = list[idx];
        if (d && d.decision_id) {
          window.location.href = window.FA.detailUrl(d.decision_id);
        }
      });
    });
  }

  // --- Filter + render ------------------------------------------------------
  function applyFiltersAndRender() {
    var list = STATE.raw || [];
    var fromStr = $from && $from.value ? $from.value : '';
    var toStr   = $to   && $to.value   ? $to.value   : '';
    var tickerF = $ticker.value ? $ticker.value.trim().toUpperCase() : '';
    var actionF = $action.value ? $action.value.toUpperCase() : '';
    var minConf = Number($confidence.value) / 100;  // 0..1
    var compF   = $compliance.value ? $compliance.value.toUpperCase() : '';

    var filtered = list.filter(function (d) {
      if (tickerF && String(d.ticker || '').toUpperCase() !== tickerF) return false;
      if (actionF && String(d.action || '').toUpperCase() !== actionF) return false;
      if (compF   && String(d.compliance_status || '').toUpperCase() !== compF) return false;
      if (Number(d.confidence) < minConf) return false;
      if (!inDateRange(d.effective_at || d.created_at, fromStr, toStr)) return false;
      return true;
    });

    $count.textContent = list.length
      ? '(' + filtered.length + ' / ' + list.length + ')'
      : '';

    if (filtered.length === 0) {
      renderEmpty('Filtreye uyan karar yok / No decisions match the filters.');
      return;
    }
    renderTable(filtered);
  }

  // --- Data load ------------------------------------------------------------
  function loadAndRender() {
    setLoading(true);
    renderError(null);

    var params = { limit: 200 };
    var tickerF = $ticker.value ? $ticker.value.trim().toUpperCase() : '';
    if (tickerF) params.ticker = tickerF;
    if ($compliance.value) params.compliance_status = $compliance.value.toUpperCase();

    window.FA.fetchJson(window.FA.API_BASE + '/v1/decisions/recent', { params: params })
      .then(function (data) {
        STATE.raw = window.FA.normalizeList(data);
        STATE.lastUpdated = Date.now();
        applyFiltersAndRender();
        $lastUpd.textContent = 'son güncelleme ' + window.FA.fmtTime(new Date());
      })
      .catch(function (err) {
        STATE.raw = [];
        applyFiltersAndRender();
        renderError('Kararlar yüklenemedi: ' + (err && err.message ? err.message : 'bilinmeyen hata'));
      })
      .then(function () { setLoading(false); });
  }

  // --- Ticker datalist ------------------------------------------------------
  function hydrateTickerDatalist() {
    if (!$datalist) return;
    window.FA.fetchJson(window.FA.API_BASE + '/v1/market/symbols', { params: { limit: 200 } })
      .then(function (data) {
        var list = window.FA.normalizeList(data);
        $datalist.innerHTML = list.map(function (s) {
          var t = s.ticker || s.symbol;
          return t ? '<option value="' + window.FA.esc(t) + '"></option>' : '';
        }).join('');
      })
      .catch(function () { /* datalist is progressive enhancement only */ });
  }

  // --- Wiring ---------------------------------------------------------------
  function attachFilterListeners() {
    // Live filter updates: input events on every control.
    [$from, $to, $ticker, $action, $compliance].forEach(function (el) {
      if (!el) return;
      el.addEventListener('input', applyFiltersAndRender);
      el.addEventListener('change', applyFiltersAndRender);
    });
    if ($confidence) {
      $confidence.addEventListener('input', function () {
        if ($confRead) $confRead.textContent = '≥ ' + $confidence.value + '%';
        applyFiltersAndRender();
      });
    }
    if ($clear) {
      $clear.addEventListener('click', function () {
        setDefaultDateRange();
        $ticker.value = '';
        $action.value = '';
        $compliance.value = '';
        $confidence.value = 0;
        if ($confRead) $confRead.textContent = '≥ 0%';
        // Re-trigger server fetch (ticker/compliance might've changed).
        loadAndRender();
      });
    }
    if ($refreshBtn) {
      $refreshBtn.addEventListener('click', function () { loadAndRender(); });
    }
  }

  // --- Bootstrap ------------------------------------------------------------
  function prefilterFromUrl() {
    var t = window.FA.getQueryParam('ticker');
    if (t) $ticker.value = String(t).toUpperCase();
  }

  function boot() {
    setDefaultDateRange();
    prefilterFromUrl();
    if ($confRead) $confRead.textContent = '≥ 0%';
    attachFilterListeners();
    hydrateTickerDatalist();
    loadAndRender();
    // 30s loop — server returns the same items, client filters change rarely.
    window.FA.attachRefreshLoop(loadAndRender, 30000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();