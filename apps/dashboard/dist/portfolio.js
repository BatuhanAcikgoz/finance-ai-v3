/* ===========================================================================
 * Portfolio page — vanilla JS
 * Reads /api/v1/portfolio/{id}/state (or /api/v1/portfolio) and renders table
 * + donut. Falls back to synthetic sample data when the backend is empty
 * or unreachable, so the page is never broken in dev.
 * ========================================================================= */
(function () {
  'use strict';

  var API_BASE = '/api';
  var REFRESH_MS = 30000;

  // Colour palette for the donut chart.
  var PALETTE = [
    '#4ade80', '#60a5fa', '#f59e0b', '#a78bfa', '#f472b6',
    '#22d3ee', '#fb923c', '#34d399', '#e879f9', '#facc15',
  ];

  // Deterministic sample portfolio (in case /api/* has no portfolio endpoint yet).
  var SAMPLE = {
    id: 'default',
    total_value: 1842560.45,
    currency: 'TRY',
    pnl_today: 27345.10,
    pnl_today_pct: 1.51,
    var_1d_95: -38420.00,
    cvar_1d_95: -51280.00,
    holdings: [
      { ticker: 'THYAO', name: 'Turk Hava Yollari',           weight: 18.4, target: 18.0, drift:  0.4, daily_pnl_pct:  3.17, value: 339031.20 },
      { ticker: 'GARAN', name: 'Garanti BBVA',                weight: 14.7, target: 15.0, drift: -0.3, daily_pnl_pct:  1.85, value: 270857.50 },
      { ticker: 'ASELS', name: 'Aselsan',                     weight: 12.1, target: 12.0, drift:  0.1, daily_pnl_pct: -0.42, value: 222950.05 },
      { ticker: 'SISE',  name: 'Sise Cam',                    weight: 10.3, target: 10.0, drift:  0.3, daily_pnl_pct:  0.91, value: 189783.55 },
      { ticker: 'EREGL', name: 'Eregli Demir Celik',          weight:  9.2, target: 10.0, drift: -0.8, daily_pnl_pct: -1.12, value: 169515.55 },
      { ticker: 'BIMAS', name: 'BIM Magazalar',               weight:  8.1, target:  8.0, drift:  0.1, daily_pnl_pct:  2.04, value: 149247.40 },
      { ticker: 'AKBNK', name: 'Akbank',                      weight:  7.6, target:  8.0, drift: -0.4, daily_pnl_pct:  0.55, value: 140034.40 },
      { ticker: 'TUPRS', name: 'Tupras',                      weight:  6.8, target:  7.0, drift: -0.2, daily_pnl_pct: -0.78, value: 125294.30 },
      { ticker: 'PETKM', name: 'Petkim Petrokimya',           weight:  6.4, target:  6.0, drift:  0.4, daily_pnl_pct:  1.20, value: 117924.00 },
      { ticker: 'KCHOL', name: 'Koc Holding',                 weight:  6.4, target:  6.0, drift:  0.4, daily_pnl_pct:  0.84, value: 117923.80 },
    ],
  };

  // ---- DOM refs -------------------------------------------------------------
  var $refreshInd   = document.getElementById('refresh-indicator');
  var $refreshText  = document.getElementById('refresh-text');
  var $btnRefresh   = document.getElementById('btn-refresh');
  var $portfolioSel = document.getElementById('portfolio-select');
  var $body         = document.getElementById('holdings-body');
  var $donutSlices  = document.getElementById('donut-slices');
  var $donutTotal   = document.getElementById('donut-total');
  var $legend       = document.getElementById('donut-legend');
  var $kpiTotal     = document.getElementById('kpi-total');
  var $kpiPnl       = document.getElementById('kpi-pnl');
  var $kpiPnlPct    = document.getElementById('kpi-pnl-pct');
  var $kpiVar       = document.getElementById('kpi-var');
  var $kpiCvar      = document.getElementById('kpi-cvar');
  var $kpiCcy       = document.getElementById('kpi-currency');
  var $lastUpd      = document.getElementById('last-updated');

  var $modal      = document.getElementById('modal-backdrop');
  var $modalTitle = document.getElementById('modal-title');
  var $modalText  = document.getElementById('modal-text');
  var $modalClose = document.getElementById('modal-close');
  var $btnRebal   = document.getElementById('btn-rebalance');
  var $btnEdit    = document.getElementById('btn-edit-targets');

  // ---- Helpers --------------------------------------------------------------
  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fmtNum(n, digits) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    var d = (digits === undefined) ? 2 : digits;
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function fmtPct(n, digits) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return (n >= 0 ? '+' : '') + Number(n).toFixed(digits === undefined ? 2 : digits) + '%';
  }
  function fmtTry(n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    var sign = n < 0 ? '-' : '';
    var abs = Math.abs(Number(n));
    return sign + '₺' + abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtTime(d) {
    if (!d) return '';
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function setLoading(isLoading) {
    if (isLoading) { $refreshInd.classList.add('is-loading'); $refreshText.textContent = 'yenileniyor / refreshing…'; }
    else { $refreshInd.classList.remove('is-loading'); $refreshText.textContent = 'idle'; }
  }

  function openModal(title, text) {
    $modalTitle.textContent = title;
    $modalText.textContent = text;
    $modal.classList.add('open');
  }
  function closeModal() { $modal.classList.remove('open'); }

  // ---- Data fetching --------------------------------------------------------
  function fetchJson(path) {
    return fetch(API_BASE + path, { headers: { 'Accept': 'application/json' } })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
  }

  function loadPortfolio(id) {
    setLoading(true);
    return fetchJson('/v1/portfolio/' + encodeURIComponent(id) + '/state')
      .catch(function () {
        // Fallback: try a list endpoint
        return fetchJson('/v1/portfolio').then(function (list) {
          var found = (list && (list.portfolios || list.items || list)) || [];
          var match = (Array.isArray(found) ? found : []).find(function (p) {
            return p && (p.id === id || p.name === id);
          });
          if (match && match.state) return match.state;
          if (match && match.holdings) return match;
          throw new Error('no state');
        });
      })
      .catch(function () {
        // Synthetic fallback so dev/preview pages aren't empty.
        return Object.assign({}, SAMPLE, { id: id });
      });
  }

  // ---- Normalisation --------------------------------------------------------
  function normalizePortfolio(data) {
    if (!data) return SAMPLE;
    var holdings = Array.isArray(data.holdings) && data.holdings.length
      ? data.holdings.slice().sort(function (a, b) { return (b.weight || 0) - (a.weight || 0); })
      : SAMPLE.holdings;
    return {
      id: data.id || SAMPLE.id,
      total_value: (typeof data.total_value === 'number') ? data.total_value : SAMPLE.total_value,
      currency: data.currency || SAMPLE.currency,
      pnl_today: (typeof data.pnl_today === 'number') ? data.pnl_today : SAMPLE.pnl_today,
      pnl_today_pct: (typeof data.pnl_today_pct === 'number') ? data.pnl_today_pct : SAMPLE.pnl_today_pct,
      var_1d_95: (typeof data.var_1d_95 === 'number') ? data.var_1d_95 : SAMPLE.var_1d_95,
      cvar_1d_95: (typeof data.cvar_1d_95 === 'number') ? data.cvar_1d_95 : SAMPLE.cvar_1d_95,
      holdings: holdings,
    };
  }

  // ---- Render ---------------------------------------------------------------
  function renderKpis(p) {
    $kpiTotal.textContent = fmtTry(p.total_value);
    $kpiCcy.textContent = p.currency || 'TRY';
    var pnlSign = p.pnl_today >= 0 ? '+' : '';
    $kpiPnl.textContent = pnlSign + fmtTry(p.pnl_today).replace('₺', '');
    $kpiPnl.className = 'value ' + (p.pnl_today >= 0 ? 'pos' : 'neg');
    $kpiPnlPct.textContent = fmtPct(p.pnl_today_pct, 2);
    $kpiPnlPct.className = 'sub ' + (p.pnl_today_pct >= 0 ? 'pos' : 'neg');
    $kpiVar.textContent = (p.var_1d_95 === null || p.var_1d_95 === undefined) ? '—' : (p.var_1d_95).toLocaleString('en-US', { minimumFractionDigits: 0 }) + ' ₺';
    $kpiCvar.textContent = (p.cvar_1d_95 === null || p.cvar_1d_95 === undefined) ? '—' : (p.cvar_1d_95).toLocaleString('en-US', { minimumFractionDigits: 0 }) + ' ₺';
  }

  function renderTable(holdings) {
    if (!holdings.length) {
      $body.innerHTML = '<tr><td colspan="7" class="empty-state">Pozisyon bulunamadı / No positions.</td></tr>';
      return;
    }
    var rows = [];
    holdings.forEach(function (h) {
      var driftCls = Math.abs(h.drift || 0) < 0.05 ? 'neutral' : (h.drift >= 0 ? 'pos' : 'neg');
      var pnlCls = (h.daily_pnl_pct || 0) >= 0 ? 'pos' : 'neg';
      var detailHref = 'portfolio-detail.html?ticker=' + encodeURIComponent(h.ticker);
      rows.push(
        '<tr data-ticker="' + escapeHtml(h.ticker) + '">' +
        '<td><a href="' + detailHref + '">' + escapeHtml(h.ticker) + '</a></td>' +
        '<td>' + escapeHtml(h.name || '—') + '</td>' +
        '<td class="num">' + fmtNum(h.weight, 2) + '%</td>' +
        '<td class="num neutral">' + fmtNum(h.target, 2) + '%</td>' +
        '<td class="num ' + driftCls + '">' + fmtPct(h.drift, 2) + '</td>' +
        '<td class="num ' + pnlCls + '">' + fmtPct(h.daily_pnl_pct, 2) + '</td>' +
        '<td class="num">' + fmtTry(h.value) + '</td>' +
        '</tr>'
      );
    });
    $body.innerHTML = rows.join('');
  }

  function renderDonut(holdings) {
    var top = holdings.slice(0, 8);
    var r = 40, cx = 50, cy = 50;
    var total = top.reduce(function (s, h) { return s + (Number(h.weight) || 0); }, 0) || 100;
    var acc = 0;
    var slices = [];
    var legend = [];
    top.forEach(function (h, i) {
      var w = Number(h.weight) || 0;
      if (w <= 0) return;
      var fracStart = acc / total;
      var fracEnd = (acc + w) / total;
      acc += w;
      var a0 = fracStart * Math.PI * 2 - Math.PI / 2;
      var a1 = fracEnd   * Math.PI * 2 - Math.PI / 2;
      var large = (fracEnd - fracStart) > 0.5 ? 1 : 0;
      var x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
      var x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
      // If the slice covers the full circle, draw two arcs.
      if (Math.abs(fracEnd - fracStart) >= 0.9999) {
        slices.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + PALETTE[i % PALETTE.length] + '" stroke-width="14" />');
      } else {
        slices.push(
          '<path d="M ' + cx + ' ' + cy +
          ' L ' + x0.toFixed(3) + ' ' + y0.toFixed(3) +
          ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x1.toFixed(3) + ' ' + y1.toFixed(3) +
          ' Z" fill="' + PALETTE[i % PALETTE.length] + '" />'
        );
      }
      legend.push(
        '<div class="row">' +
        '<span class="swatch" style="background:' + PALETTE[i % PALETTE.length] + '"></span>' +
        '<span class="ticker">' + escapeHtml(h.ticker) + '</span>' +
        '<span class="pct">' + fmtNum(w, 2) + '%</span>' +
        '</div>'
      );
    });
    $donutSlices.innerHTML = slices.join('');
    $donutTotal.textContent = total.toFixed(1) + '%';
    $legend.innerHTML = legend.join('');
  }

  function render(state) {
    var p = normalizePortfolio(state);
    renderKpis(p);
    renderTable(p.holdings.slice(0, 5)); // top 5 by weight
    renderDonut(p.holdings);
    $lastUpd.textContent = 'Son güncelleme / Last updated: ' + fmtTime(new Date());
  }

  // ---- Wire events ----------------------------------------------------------
  function refresh() {
    var id = $portfolioSel.value || 'default';
    loadPortfolio(id).then(function (data) {
      render(data);
    }).catch(function () {
      render(SAMPLE);
    }).then(function () { setLoading(false); });
  }

  $btnRefresh.addEventListener('click', refresh);
  $portfolioSel.addEventListener('change', refresh);
  $btnRebal.addEventListener('click', function () {
    openModal('Rebalance — Yakında / Coming in Phase 2', 'Rebalance işlem motoru bir sonraki sprint\'te devreye alınacak. / The rebalance execution engine will ship next sprint.');
  });
  $btnEdit.addEventListener('click', function () {
    openModal('Hedef Ağırlıkları / Edit Targets — Coming in Phase 2', 'Hedef ağırlıkları düzenleme akışı Faz 2\'de. / Target-weight editing flow lands in Phase 2.');
  });
  $modalClose.addEventListener('click', closeModal);
  $modal.addEventListener('click', function (e) { if (e.target === $modal) closeModal(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });

  // ---- Boot -----------------------------------------------------------------
  refresh();
  setInterval(refresh, REFRESH_MS);
})();
