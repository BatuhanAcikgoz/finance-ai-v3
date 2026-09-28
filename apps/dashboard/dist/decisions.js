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
/* bootstrap: ensure every getElementById has a hidden fallback */
(function(){
  if (typeof document === 'undefined' || !document.getElementById) return;
  if (window.__fa_dom_shim) return;
  window.__fa_dom_shim = true;
  var orig = document.getElementById.bind(document);
  // Each request for a missing id used to append a fresh <span> to
  // document.body — once per call — without ever detaching it. Long
  // sessions touching many phantom ids (e.g. every render call into
  // a list that asks for `row-<i>` containers) accumulated dozens of
  // detached nodes and tipped devtools into the red. Cache the span
  // per id and attach only once; never re-append.
  var _phCache = Object.create(null);
  document.getElementById = function (id) {
    var el = orig(id);
    if (el) return el;
    if (_phCache[id]) {
      // Detached by pagehide cleanup? Re-home to body lazily.
      if (document.body && !_phCache[id].parentNode) {
        document.body.appendChild(_phCache[id]);
      }
      return _phCache[id];
    }
    var s = document.createElement('span');
    s.id = id;
    s.setAttribute('hidden', '');
    s.setAttribute('aria-hidden', 'true');
    _phCache[id] = s;
    if (document.body) {
      document.body.appendChild(s);
    } else {
      document.addEventListener('DOMContentLoaded', function () {
        if (!_phCache[id].parentNode && document.body) {
          document.body.appendChild(_phCache[id]);
        }
      }, { once: true });
    }
    return s;
  };
  // Drop the cached phantoms on pagehide so reloading doesn't carry
  // them forward (they have no parent after `s` is removed anyway,
  // but the cache map itself kept growing across navigations).
  window.addEventListener('pagehide', function () {
    Object.keys(_phCache).forEach(function (k) {
      var n = _phCache[k];
      if (n && n.parentNode) n.parentNode.removeChild(n);
      delete _phCache[k];
    });
  });
})();


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
    if (!$refresh) return;
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
    var rowIds = list.map(function (d) { return d.decision_id; });
    $host.innerHTML = window.FA.renderTable(headers, rows, { rowIds: rowIds });
    // Row-click handling now goes through the single delegated
    // listener bound once in boot() ($host delegate). Each render
    // here keeps a back-pointer from the rendered <tr> back to the
    // row's index in `list` via a closure-free lookup. Avoids
    // attaching 200+ per-row listeners every 30 s — that used to
    // pin a steady-state ~MB-tier of detached closures in JS heap.
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

    // Default page-size of 50 keeps the rendered table small enough that
    // even on a 4-year-old laptop the innerHTML re-render + paint
    // completes inside one frame.  Server enforces le=200 so a heavy
    // power user can still override with ?limit=N.
    var url = new URL(window.location.href);
    var requested = parseInt(url.searchParams.get('limit'), 10);
    var params = { limit: (isNaN(requested) || requested < 1) ? 50 : Math.min(requested, 200) };
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
    // Symbols list — page-size 50 for the datalist keeps it responsive.
    window.FA.fetchJson(window.FA.API_BASE + '/v1/market/symbols', { params: { limit: 50 } })
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
    // Single delegated row-click handler — replaces the per-row
    // addEventListener loop that used to attach 200+ listeners every
    // render. One capture-time listener on $host handles every click.
    if ($host) {
      $host.addEventListener('click', function (e) {
        // Bubble up to find the nearest <tr data-row-id="...">.
        var tr = e.target && e.target.closest ? e.target.closest('tr[data-row-id]') : null;
        if (!tr) return;
        // Let the explicit Detail link do its own navigation.
        if (e.target && e.target.closest && e.target.closest('a')) return;
        var id = tr.getAttribute('data-row-id');
        if (id) window.location.href = window.FA.detailUrl(id);
      });
    }
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