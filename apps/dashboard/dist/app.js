/* ===========================================================================
 * Finance AI V3 — Dashboard (vanilla JS, no build step)
 * Single-page overview rendered against the running api-gateway stack:
 *   /api/health/ready                    — system pill (poll 10s)
 *   /api/v1/market/symbols               — ticker universe
 *   /api/v1/market/ohlcv/{ticker}?limit=… — bars for LAST/Δ%/VOL + sparklines
 *   /api/v1/decisions/recent?limit=5     — today's decisions top 5
 *
 * Auto-refresh every 15s; sparkline click panel uses 50 bars.
 * Inline SVG only (no chart lib). Light + dark via CSS variables.
 * =========================================================================== */
(function () {
  'use strict';

  // ---- Config ---------------------------------------------------------------
  var API_BASE = '/api';                       // nginx /api/* → api-gateway
  var REFRESH_MS = 15000;
  var HEALTH_MS = 10000;
  var ROW_BARS = 30;                           // mini sparkline bars
  var PANEL_BARS = 50;                         // click panel sparkline bars
  var MAX_TICKERS = 30;                        // cap to keep first paint snappy

  // ---- DOM refs -------------------------------------------------------------
  var $health        = document.getElementById('health-badge');
  var $symBody       = document.getElementById('symbols-body');
  var $symCount      = document.getElementById('symbols-count');
  var $decisionsList = document.getElementById('decisions-list');
  var $decisionsCount= document.getElementById('decisions-count');
  var $portfolioNote = document.getElementById('portfolio-note');
  var $portfolioTbl  = document.getElementById('portfolio-table');
  var $portfolioBody = document.getElementById('portfolio-body');
  var $alertsList    = document.getElementById('alerts-list');
  var $moversList    = document.getElementById('movers-list');
  var $bist100val    = document.getElementById('bist100-val');
  var $bist100chg    = document.getElementById('bist100-chg');
  var $usdtryval     = document.getElementById('usdtry-val');
  var $usdtrychg     = document.getElementById('usdtry-chg');
  var $eurotryval    = document.getElementById('eurotry-val');
  var $eurotrychg    = document.getElementById('eurotry-chg');
  var $chartSymbol   = document.getElementById('chart-symbol');
  var $chartPrice    = document.getElementById('chart-price');
  var $chartBody     = document.getElementById('chart-body');
  var $chartMeta     = document.getElementById('chart-meta');
  var $refresh       = document.getElementById('refresh-indicator');
  var $lastUpd       = document.getElementById('last-updated');
  var $lastUpdFoot   = document.getElementById('last-updated-footer');
  var $kpiPortVal    = document.getElementById('kpi-portfolio-value');
  var $kpiPortSub    = document.getElementById('kpi-portfolio-sub');
  var $kpiPnlVal     = document.getElementById('kpi-pnl-value');
  var $kpiPnlSub     = document.getElementById('kpi-pnl-sub');
  var $kpiVarVal     = document.getElementById('kpi-var-value');
  var $kpiVarSub     = document.getElementById('kpi-var-sub');
  var $kpiDecVal     = document.getElementById('kpi-decisions-value');
  var $kpiDecSub     = document.getElementById('kpi-decisions-sub');

  var activeSymbol = null;
  var lastSymbolList = [];                     // tickers currently rendered

  // ---- Helpers --------------------------------------------------------------
  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fmtNum(n, digits) {
    if (n === null || n === undefined || n === '' || isNaN(Number(n))) return '—';
    var d = (digits === undefined) ? 2 : digits;
    return Number(n).toLocaleString('en-US', {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }

  // Turkish-style currency: ₺1.234,56 (uses locale de-DE which already does dots/commas)
  function fmtTRY(n, digits) {
    if (n === null || n === undefined || n === '' || isNaN(Number(n))) return '—';
    var d = (digits === undefined) ? 2 : digits;
    var s = Number(n).toLocaleString('de-DE', {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
    return '₺' + s;
  }

  function fmtPct(n) {
    if (n === null || n === undefined || n === '' || isNaN(Number(n))) return { text: '—', cls: 'neutral', sign: '' };
    var v = Number(n);
    var sign = v >= 0 ? '+' : '';
    var cls = v >= 0 ? 'pos' : 'neg';
    return { text: sign + v.toFixed(2) + '%', cls: cls, sign: sign, val: v };
  }

  function fmtVol(n) {
    if (n === null || n === undefined || n === '' || isNaN(Number(n))) return '—';
    n = Number(n);
    if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(2) + 'K';
    return String(Math.round(n));
  }

  function fmtTime(d) {
    try {
      var dt = (d instanceof Date) ? d : new Date(d);
      if (isNaN(dt.getTime())) return '';
      return dt.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) { return ''; }
  }

  function fmtDateShort(d) {
    try {
      var dt = (d instanceof Date) ? d : new Date(d);
      if (isNaN(dt.getTime())) return '';
      return dt.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' });
    } catch (e) { return ''; }
  }

  function setLoading(on) {
    if (on) $refresh.classList.add('is-loading');
    else    $refresh.classList.remove('is-loading');
  }

  function setKpiEmpty($val, $sub, msg) {
    $val.textContent = '—';
    $val.classList.add('is-empty');
    if ($sub) $sub.textContent = msg || '—';
  }

  // ---- Network --------------------------------------------------------------
  /** GET JSON; resolves parsed body on 2xx, rejects with Error(.status) otherwise. */
  function fetchJson(path, opts) {
    opts = opts || {};
    var url = path;
    if (opts.params) {
      var qs = Object.keys(opts.params)
        .filter(function (k) { return opts.params[k] !== undefined && opts.params[k] !== null; })
        .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(opts.params[k]); })
        .join('&');
      if (qs) url += (path.indexOf('?') >= 0 ? '&' : '?') + qs;
    }
    return fetch(url, {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
    }).then(function (res) {
      if (!res.ok) {
        var err = new Error('HTTP ' + res.status + ' on ' + path);
        err.status = res.status;
        throw err;
      }
      return res.json();
    });
  }

  function normalizeList(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.items))    return data.items;
    if (data && Array.isArray(data.symbols))  return data.symbols;
    if (data && Array.isArray(data.decisions))return data.decisions;
    if (data && Array.isArray(data.bars))     return data.bars;
    if (data && Array.isArray(data.indices))  return data.indices;
    return [];
  }

  // ===========================================================================
  // HEALTH
  // ===========================================================================
  function renderHealth(state, label) {
    if (!$health) return;  // safe no-op on pages without the badge
    $health.classList.remove('online', 'degraded', 'offline');
    if (state) $health.classList.add(state);
    var lblEl = $health.querySelector('.label');
    if (lblEl) lblEl.textContent = label;
  }

  function pollHealth() {
    // /api/health returns 307→/api/health/ which returns 200 {status:healthy}.
    // /api/health/ready returns the full per-dep breakdown — that's what we want.
    fetchJson(API_BASE + '/health/ready')
      .then(function (data) {
        var status = (data && data.status) ? String(data.status).toLowerCase() : '';
        // Per spec: online=green, degraded=amber, offline=red.
        if (status === 'ready' || status === 'healthy' || status === 'alive' || status === 'ok') {
          renderHealth('online', 'online');
        } else if (status === 'degraded') {
          renderHealth('degraded', 'degraded');
        } else {
          renderHealth('degraded', status || 'unknown');
        }
      })
      .catch(function () { renderHealth('offline', 'offline'); });
  }

  // ===========================================================================
  // SYMBOLS + LAST/Δ%/VOL (computed client-side from latest 2 bars per spec)
  // ===========================================================================
  /**
   * Build LAST/Δ%/VOL for a single ticker from its latest 2 bars.
   * The /ohlcv endpoint returns bars in DESC order (newest first), so
   * bar[0] is the latest and bar[1] is the previous.
   */
  function computeLastChange(bars) {
    if (!Array.isArray(bars) || bars.length === 0) {
      return { last: null, prev: null, change: null, volume: null };
    }
    var latest = bars[0];
    var prev = bars[1];
    var last = num(latest && (latest.close !== undefined ? latest.close : latest.c));
    var prevClose = prev ? num(prev.close !== undefined ? prev.close : prev.c) : null;
    var change = (last !== null && prevClose !== null && prevClose !== 0)
      ? ((last - prevClose) / prevClose) * 100
      : null;
    var volume = num(latest && latest.volume);
    return { last: last, prev: prevClose, change: change, volume: volume };
  }

  function num(v) {
    if (v === null || v === undefined || v === '' || isNaN(Number(v))) return null;
    return Number(v);
  }

  /**
   * Render the symbols table.
   * Each row carries its own mini 30-bar sparkline (inline SVG).
   * LAST/Δ%/VOL are derived from /v1/market/ohlcv/{t}?limit=2 — so
   * "real LAST" per spec is computed client-side from the two most
   * recent bars (not the server's /quote endpoint).
   */
  function renderSymbolRow(t, computed) {
    var pct = computed.change;
    var cls = pct === null ? 'neutral' : (pct >= 0 ? 'pos' : 'neg');
    var sign = pct === null ? '' : (pct >= 0 ? '+' : '');
    var pctTxt = pct === null ? '—' : (sign + pct.toFixed(2) + '%');
    var sparkColor = pct === null
      ? 'var(--muted-foreground)'
      : (pct >= 0 ? 'var(--bullish)' : 'var(--bearish)');
    var intensity = pct === null ? 0.4 : Math.min(0.55, 0.18 + Math.min(Math.abs(pct), 5) / 12);
    var miniSpark = '';  // filled in later when mini bars resolve
    return ''
      + '<tr data-symbol="' + escapeHtml(t) + '">'
      +   '<td><strong>' + escapeHtml(t) + '</strong></td>'
      +   '<td>' + escapeHtml(t) + '</td>'
      +   '<td class="num mono">' + (computed.last === null ? '—' : fmtNum(computed.last)) + '</td>'
      +   '<td class="num ' + cls + '">' + pctTxt + '</td>'
      +   '<td class="num">' + (computed.volume === null ? '—' : fmtVol(computed.volume)) + '</td>'
      +   '<td><span class="spark-mini" data-spark-color="' + sparkColor + '" data-intensity="' + intensity.toFixed(3) + '">' + miniSpark + '</span></td>'
      + '</tr>';
  }

  function renderSymbolsShell(tickers) {
    if (!tickers.length) {
      $symBody.innerHTML = '<tr><td colspan="6" class="empty-state">Sembol bulunamadı.</td></tr>';
      $symCount.textContent = '0 adet';
      return;
    }
    // Initial pass: placeholders. Numbers and sparklines filled in async.
    $symBody.innerHTML = tickers.map(function (t) {
      return ''
        + '<tr data-symbol="' + escapeHtml(t) + '">'
        +   '<td><strong>' + escapeHtml(t) + '</strong></td>'
        +   '<td>' + escapeHtml(t) + '</td>'
        +   '<td class="num mono">…</td>'
        +   '<td class="num neutral">…</td>'
        +   '<td class="num">…</td>'
        +   '<td><span class="spark-mini" data-spark-color="var(--muted-foreground)"></span></td>'
        + '</tr>';
    }).join('');
    $symCount.textContent = tickers.length + ' adet';
    wireRowClicks();
    if (activeSymbol) highlightActiveRow(activeSymbol);
  }

  function wireRowClicks() {
    var rows = $symBody.querySelectorAll('tr[data-symbol]');
    Array.prototype.forEach.call(rows, function (tr) {
      tr.addEventListener('click', function () {
        var sym = tr.getAttribute('data-symbol');
        selectSymbol(sym);
      });
    });
  }

  function highlightActiveRow(sym) {
    var rows = $symBody.querySelectorAll('tr[data-symbol]');
    Array.prototype.forEach.call(rows, function (tr) {
      if (tr.getAttribute('data-symbol') === sym) tr.classList.add('is-active');
      else tr.classList.remove('is-active');
    });
  }

  /**
   * Fetch /v1/market/ohlcv/{t}?limit=2 → compute LAST/Δ%/VOL client-side per spec.
   * Also fetch /v1/market/ohlcv/{t}?limit=30 for the inline mini sparkline.
   * Updates the corresponding row in place to avoid full re-render flicker.
   */
  function hydrateSymbolRow(t) {
    var tr = $symBody.querySelector('tr[data-symbol="' + cssEscape(t) + '"]');
    if (!tr) return Promise.resolve();

    var tds = tr.children;
    var $last = tds[2];
    var $pct  = tds[3];
    var $vol  = tds[4];
    var $spark= tds[5].querySelector('.spark-mini');

    // ---- LAST + Δ% + VOL from 2 bars ----
    var lastPromise = fetchJson(API_BASE + '/v1/market/ohlcv/' + encodeURIComponent(t), {
      params: { limit: 2 }
    }).then(function (data) {
      var bars = (data && data.bars) ? data.bars : (Array.isArray(data) ? data : []);
      var c = computeLastChange(bars);
      $last.textContent = c.last === null ? '—' : fmtNum(c.last);
      if (c.change === null) {
        $pct.textContent = '—';
        $pct.className = 'num neutral';
      } else {
        var sign = c.change >= 0 ? '+' : '';
        $pct.textContent = sign + c.change.toFixed(2) + '%';
        $pct.className = 'num ' + (c.change >= 0 ? 'pos' : 'neg');
      }
      $vol.textContent = c.volume === null ? '—' : fmtVol(c.volume);
      return c;
    }).catch(function () {
      $last.textContent = '—';
      $pct.textContent = '—'; $pct.className = 'num neutral';
      $vol.textContent = '—';
      return null;
    });

    // ---- Mini sparkline from 30 bars ----
    var sparkPromise = fetchJson(API_BASE + '/v1/market/ohlcv/' + encodeURIComponent(t), {
      params: { limit: ROW_BARS }
    }).then(function (data) {
      var bars = (data && data.bars) ? data.bars : (Array.isArray(data) ? data : []);
      renderMiniSparkline($spark, bars, t);
      return bars;
    }).catch(function () {
      $spark.innerHTML = '';
      return [];
    });

    return Promise.all([lastPromise, sparkPromise]);
  }

  function cssEscape(s) {
    // Defensive — tickers are uppercase letters/digits but be safe.
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  // ===========================================================================
  // MINI SPARKLINE (inline SVG, 30 bars, color = sign of change)
  // ===========================================================================
  function renderMiniSparkline(host, bars, symbol) {
    if (!host) return;
    var closes = bars.map(function (b) {
      var v = (b && (b.close !== undefined ? b.close : b.c));
      return (v === undefined || v === null || isNaN(Number(v))) ? null : Number(v);
    }).filter(function (v) { return v !== null; });

    if (closes.length < 2) {
      host.innerHTML = '';
      return;
    }
    // Spec: green if Δ%>0 else red; intensity proportional to magnitude.
    var pct = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;
    var bull = pct >= 0;
    var intensity = Math.min(0.65, 0.2 + Math.min(Math.abs(pct), 5) / 10);
    var stroke = bull ? 'var(--bullish)' : 'var(--bearish)';
    var fill   = bull ? 'var(--bullish)' : 'var(--bearish)';

    var W = 80, H = 22, PAD = 1;
    var min = Math.min.apply(null, closes);
    var max = Math.max.apply(null, closes);
    var span = (max - min) || 1;
    var stepX = (W - PAD * 2) / (closes.length - 1);
    function x(i) { return PAD + i * stepX; }
    function y(v) { return H - PAD - ((v - min) / span) * (H - PAD * 2); }

    var points = closes.map(function (v, i) { return x(i).toFixed(2) + ',' + y(v).toFixed(2); }).join(' ');
    var linePath = 'M ' + points.split(' ').join(' L ');
    var areaPath = linePath
      + ' L ' + x(closes.length - 1).toFixed(2) + ',' + (H - PAD)
      + ' L ' + x(0).toFixed(2) + ',' + (H - PAD) + ' Z';

    // Spec: Apple system gradient stroke (accent → accent-tertiary).
    var gradId = 'sparkGrad-' + symbol.replace(/[^a-zA-Z0-9_-]/g, '_');
    var areaOpacity = (intensity * 0.35).toFixed(3);

    host.innerHTML = ''
      + '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" '
      +     'role="img" aria-label="' + escapeHtml(symbol) + ' sparkline" '
      +     'style="width:100%;height:100%;">'
      +   '<defs>'
      +     '<linearGradient id="' + gradId + '" x1="0" y1="0" x2="1" y2="0">'
      +       '<stop offset="0%"  stop-color="var(--accent)"/>'
      +       '<stop offset="100%" stop-color="var(--accent-tertiary)"/>'
      +     '</linearGradient>'
      +   '</defs>'
      +   '<path d="' + areaPath + '" fill="url(#' + gradId + ')" fill-opacity="' + areaOpacity + '" stroke="none"/>'
      +   '<path d="' + linePath + '" fill="none" stroke="url(#' + gradId + ')" stroke-width="1.6" '
      +         'stroke-opacity="' + intensity.toFixed(3) + '" stroke-linecap="round" stroke-linejoin="round"/>'
      + '</svg>';
  }

  // ===========================================================================
  // CLICK PANEL SPARKLINE (50 bars)
  // ===========================================================================
  function renderPanelSparkline(bars, symbol) {
    if (!Array.isArray(bars) || bars.length === 0) {
      $chartBody.innerHTML = '<div class="chart-empty">Bu sembol için OHLCV verisi yok.</div>';
      $chartMeta.textContent = '—';
      return;
    }
    // Endpoint returns DESC; render oldest → newest (left → right) for clarity.
    var ordered = bars.slice().reverse();
    var closes = ordered.map(function (b) {
      var v = b.close !== undefined ? b.close : b.c;
      return (v === undefined || v === null || isNaN(Number(v))) ? null : Number(v);
    });
    var valid = closes.filter(function (v) { return v !== null; });
    if (valid.length < 2) {
      $chartBody.innerHTML = '<div class="chart-empty">Grafik için yeterli veri yok.</div>';
      return;
    }

    var W = 900, H = 160, PAD_L = 50, PAD_R = 16, PAD_T = 14, PAD_B = 26;
    var plotW = W - PAD_L - PAD_R;
    var plotH = H - PAD_T - PAD_B;

    var min = Math.min.apply(null, valid);
    var max = Math.max.apply(null, valid);
    var span = (max - min) || 1;
    var stepX = plotW / (closes.length - 1);
    function x(i) { return PAD_L + i * stepX; }
    function y(v) { return PAD_T + plotH - ((v - min) / span) * plotH; }

    var pct = ((valid[valid.length - 1] - valid[0]) / valid[0]) * 100;
    var bull = pct >= 0;
    var lineCls  = bull ? 'line-bull' : 'line-bear';
    var areaCls  = bull ? 'area-bull' : 'area-bear';
    var dotCls   = bull ? 'dot-last-bull' : 'dot-last-bear';

    // Build line + area paths skipping null closes (draw segments between non-null neighbors).
    var segments = [];
    var currentSeg = [];
    for (var i = 0; i < closes.length; i++) {
      if (closes[i] !== null) {
        currentSeg.push([i, closes[i]]);
      } else if (currentSeg.length) {
        segments.push(currentSeg);
        currentSeg = [];
      }
    }
    if (currentSeg.length) segments.push(currentSeg);

    var pathsHtml = segments.map(function (seg) {
      if (seg.length < 2) return '';
      var pts = seg.map(function (p) { return x(p[0]).toFixed(2) + ',' + y(p[1]).toFixed(2); }).join(' L ');
      var lp = 'M ' + pts;
      var ap = lp
        + ' L ' + x(seg[seg.length - 1][0]).toFixed(2) + ',' + (PAD_T + plotH)
        + ' L ' + x(seg[0][0]).toFixed(2)              + ',' + (PAD_T + plotH)
        + ' Z';
      return '<path class="' + areaCls + '" d="' + ap + '"/>'
           + '<path class="' + lineCls + '" d="' + lp + '"/>';
    }).join('');

    // Y axis labels: 3 ticks (min, mid, max)
    var ticksHtml = [min, min + span / 2, max].map(function (v) {
      return '<text x="' + (PAD_L - 6) + '" y="' + (y(v) + 4).toFixed(1) + '" '
           + 'fill="var(--muted-foreground)" font-size="10" text-anchor="end" font-family="ui-monospace,monospace">'
           + fmtNum(v) + '</text>'
           + '<line class="grid-line" x1="' + PAD_L + '" y1="' + y(v).toFixed(1) + '" '
           + 'x2="' + (W - PAD_R) + '" y2="' + y(v).toFixed(1) + '"/>';
    }).join('');

    // X axis labels: first, mid, last
    var xLabels = [0, Math.floor(closes.length / 2), closes.length - 1];
    var xLabelsHtml = xLabels.map(function (idx) {
      var bar = ordered[idx];
      var label = bar && bar.ts ? fmtDateShort(bar.ts) : '';
      return '<text x="' + x(idx).toFixed(1) + '" y="' + (H - 8) + '" '
           + 'fill="var(--muted-foreground)" font-size="10" text-anchor="middle" font-family="ui-monospace,monospace">'
           + label + '</text>';
    }).join('');

    var lastVal = valid[valid.length - 1];
    var lastIdx = closes.length - 1;
    var lastX = x(lastIdx);
    var lastY = y(lastVal);

    var pctInfo = fmtPct(pct);
    $chartPrice.innerHTML = fmtNum(lastVal)
      + ' <span class="' + pctInfo.cls + '" style="font-size:13px">(' + pctInfo.text + ')</span>';
    $chartMeta.textContent = bars.length + ' bar · ' + (ordered[0] && ordered[0].timeframe ? ordered[0].timeframe : '1d');

    $chartBody.innerHTML = ''
      + '<svg class="sparkline" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" role="img" '
      +     'aria-label="' + escapeHtml(symbol) + ' OHLCV sparkline">'
      +   ticksHtml
      +   xLabelsHtml
      +   pathsHtml
      +   '<circle class="' + dotCls + '" cx="' + lastX.toFixed(2) + '" cy="' + lastY.toFixed(2) + '" r="3.5"/>'
      + '</svg>';
  }

  // ===========================================================================
  // DECISIONS (top 5 of today)
  // ===========================================================================
  function renderDecisions(list) {
    if (!Array.isArray(list) || list.length === 0) {
      $decisionsList.innerHTML = '<li class="empty-state">No recent decisions yet.</li>';
      $decisionsCount.textContent = '0 adet';
      setKpiEmpty($kpiDecVal, $kpiDecSub, 'bugün 0 karar');
      return;
    }
    var top5 = list.slice(0, 5);
    $decisionsList.innerHTML = top5.map(function (d) {
      var action = String(d.action || d.side || 'HOLD').toUpperCase();
      var tagCls = (action === 'BUY') ? 'buy'
                 : (action === 'SELL') ? 'sell'
                 : (action === 'REDUCE') ? 'reduce'
                 : (action === 'HOLD') ? 'hold'
                 : 'idx';
      var conf = (d.confidence !== undefined && d.confidence !== null)
        ? Math.round(Number(d.confidence) * 100) + '% conf'
        : '';
      var size = (d.position_size_pct !== undefined && d.position_size_pct !== null)
        ? (Number(d.position_size_pct) * 100).toFixed(1) + '% size'
        : '';
      var ts = d.created_at || d.effective_at || null;
      var reason = (d.supervisor_reasoning || d.reason || '').toString();
      if (reason.length > 80) reason = reason.slice(0, 78) + '…';
      var metaBits = [fmtTime(ts), conf, size].filter(Boolean);
      return ''
        + '<li class="decision">'
        +   '<span class="tag ' + tagCls + '">' + escapeHtml(action) + '</span>'
        +   '<div>'
        +     '<div class="decision-symbol">' + escapeHtml(d.ticker || d.symbol || '?') + '</div>'
        +     '<div class="decision-reason">' + escapeHtml(reason || '—') + '</div>'
        +   '</div>'
        +   '<span class="decision-meta">' + escapeHtml(metaBits.join(' · ')) + '</span>'
        + '</li>';
    }).join('');
    $decisionsCount.textContent = top5.length + ' / ' + list.length + ' adet';
    $kpiDecVal.textContent = list.length;
    $kpiDecVal.classList.remove('is-empty');
    $kpiDecSub.textContent = 'bugün';
  }

  // ===========================================================================
  // PORTFOLIO (skeleton — endpoint not ready)
  // ===========================================================================
  function renderPortfolioSkeleton() {
    // Defensive: on non-home pages (decisions.html, decision-detail.html,
    // alerts.html, etc.) these DOM nodes don't exist — silently skip rather
    // than throw, so the per-page scripts that depend on window.FA still boot.
    if ($portfolioTbl)  $portfolioTbl.hidden = true;
    if ($portfolioNote) $portfolioNote.style.display = 'block';
    if ($kpiPortVal) setKpiEmpty($kpiPortVal, $kpiPortSub, 'portföy state endpoint\'i hazır olduğunda canlı değer');
    if ($kpiPnlVal)  setKpiEmpty($kpiPnlVal,  $kpiPnlSub,  'portföy state endpoint\'i hazır olduğunda günlük K/Z');
    if ($kpiVarVal)  setKpiEmpty($kpiVarVal,  $kpiVarSub,  'risk servisi hazır olduğunda VaR (1g, %95)');
  }

  // ===========================================================================
  // ALERTS (skeleton — endpoint not ready, keep "no alerts yet")
  // ===========================================================================
  function renderAlertsSkeleton() {
    if ($alertsList) $alertsList.innerHTML = '<div class="empty-state">Henüz uyarı yok.</div>';
  }

  // ===========================================================================
  // MARKET SNAPSHOT (BIST-100, USD/TRY, top movers)
  // ===========================================================================
  function renderMarketSkeleton() {
    if ($bist100val) $bist100val.textContent = '—';
    if ($bist100chg) { $bist100chg.textContent = '—'; $bist100chg.className = 'chg neutral'; }
    if ($usdtryval)  $usdtryval.textContent  = '—';
    if ($usdtrychg)  { $usdtrychg.textContent  = '—'; $usdtrychg.className  = 'chg neutral'; }
    if ($eurotryval) $eurotryval.textContent = '—';
    if ($eurotrychg) { $eurotrychg.textContent = '—'; $eurotrychg.className = 'chg neutral'; }
    if ($moversList) $moversList.innerHTML = '<div class="empty-state" style="padding:8px;">En hareketliler, endeks verisi gelince listelenecek.</div>';
  }

  /**
   * Compute top movers from already-loaded per-ticker computed bars.
   * Falls back to the symbols list when no bar data is available.
   */
  function renderMovers(tickers) {
    if (!tickers.length) {
      $moversList.innerHTML = '<div class="empty-state" style="padding:8px;">Veri bekleniyor.</div>';
      return;
    }
    var rows = tickers.map(function (t) {
      return { ticker: t.ticker, change: t.change === null ? null : Number(t.change), last: t.last };
    }).filter(function (r) { return r.change !== null && !isNaN(r.change); });

    if (!rows.length) {
      $moversList.innerHTML = '<div class="empty-state" style="padding:8px;">Hareketliler yükleniyor…</div>';
      return;
    }
    var top = rows.slice().sort(function (a, b) { return b.change - a.change; }).slice(0, 3);
    var bot = rows.slice().sort(function (a, b) { return a.change - b.change; }).slice(0, 3);
    function row(r) {
      var cls = r.change >= 0 ? 'pos' : 'neg';
      var sign = r.change >= 0 ? '+' : '';
      return '<div class="mover-row">'
           +   '<span><strong>' + escapeHtml(r.ticker) + '</strong></span>'
           +   '<span class="mono">' + (r.last === null ? '—' : fmtNum(r.last)) + '</span>'
           +   '<span class="' + cls + ' mono">' + sign + r.change.toFixed(2) + '%</span>'
           + '</div>';
    }
    $moversList.innerHTML = ''
      + '<div style="font-size:11px;color:var(--muted-foreground);text-transform:uppercase;letter-spacing:.04em;margin-top:2px;">Yükselenler</div>'
      + top.map(row).join('')
      + '<div style="font-size:11px;color:var(--muted-foreground);text-transform:uppercase;letter-spacing:.04em;margin-top:6px;">Düşenler</div>'
      + bot.map(row).join('');
  }

  function renderIndexTile($val, $chg, label, value, change) {
    $val.textContent = value === null || value === undefined ? '—' : fmtNum(value);
    var p = fmtPct(change);
    $chg.textContent = p.text;
    $chg.className = 'chg ' + p.cls;
  }

  // ===========================================================================
  // DATA LOADERS
  // ===========================================================================
  function loadSymbols() {
    return fetchJson(API_BASE + '/v1/market/symbols', { params: { limit: MAX_TICKERS } })
      .then(function (data) {
        var list = normalizeList(data).filter(function (s) {
          return s && (s.is_index === false || s.is_index === undefined);
        });
        if (!list.length) {
          $symBody.innerHTML = '<tr><td colspan="6" class="empty-state">Aktif sembol bulunamadı.</td></tr>';
          $symCount.textContent = '0 adet';
          return [];
        }
        var tickers = list.map(function (s) {
          return {
            ticker: s.ticker || s.symbol,
            name:   s.name   || s.ticker || s.symbol,
            sector: s.sector || '',
          };
        }).filter(function (t) { return !!t.ticker; });
        lastSymbolList = tickers;
        renderSymbolsShell(tickers.map(function (t) { return t.ticker; }));
        // Hydrate each row in parallel — bounded by MAX_TICKERS.
        return Promise.all(tickers.map(hydrateSymbolRow)).then(function () {
          renderMoversFromCache();
          return tickers;
        });
      })
      .catch(function () {
        $symBody.innerHTML = '<tr><td colspan="6" class="empty-state">Sembol servisi yanıt vermiyor.</td></tr>';
        $symCount.textContent = '— adet';
        return [];
      });
  }

  function renderMoversFromCache() {
    var rows = [];
    var trs = $symBody.querySelectorAll('tr[data-symbol]');
    Array.prototype.forEach.call(trs, function (tr) {
      var sym = tr.getAttribute('data-symbol');
      var tds = tr.children;
      var pctTxt = (tds[3] && tds[3].textContent || '').trim();
      var lastTxt = (tds[2] && tds[2].textContent || '').trim();
      var pct = parseFloat(pctTxt.replace('%', '').replace('+', ''));
      var last = parseFloat(lastTxt.replace(/[^0-9.\-]/g, ''));
      if (!isNaN(pct)) rows.push({ ticker: sym, change: pct, last: isNaN(last) ? null : last });
    });
    renderMovers(rows);
  }

  function loadDecisions() {
    return fetchJson(API_BASE + '/v1/decisions/recent', { params: { limit: 5 } })
      .then(function (data) {
        renderDecisions(normalizeList(data));
      })
      .catch(function () {
        renderDecisions([]);
      });
  }

  function loadPanel(symbol) {
    if (!symbol) return Promise.resolve();
    $chartSymbol.textContent = symbol;
    $chartPrice.textContent = '';
    $chartMeta.textContent = 'yükleniyor…';
    $chartBody.innerHTML = '<div class="chart-empty">' + escapeHtml(symbol) + ' yükleniyor…</div>';
    return fetchJson(API_BASE + '/v1/market/ohlcv/' + encodeURIComponent(symbol), {
      params: { limit: PANEL_BARS }
    })
      .then(function (data) {
        var bars = (data && data.bars) ? data.bars : (Array.isArray(data) ? data : []);
        renderPanelSparkline(bars, symbol);
      })
      .catch(function () {
        $chartBody.innerHTML = '<div class="chart-empty">Bu sembol için grafik yüklenemedi.</div>';
        $chartMeta.textContent = 'hata';
      });
  }

  function selectSymbol(symbol) {
    if (!symbol) return;
    activeSymbol = symbol;
    highlightActiveRow(symbol);
    loadPanel(symbol);
  }

  // ===========================================================================
  // ORCHESTRATION
  // ===========================================================================
  function setUpdated(ts) {
    var t = fmtTime(ts);
    if ($lastUpd)     $lastUpd.textContent     = t ? 'son güncelleme ' + t : '';
    if ($lastUpdFoot) $lastUpdFoot.textContent = t ? 'son güncelleme ' + t : '';
  }

  function refreshAll() {
    setLoading(true);
    var ts = Date.now();
    Promise.all([
      loadSymbols(),
      loadDecisions(),
    ])
      .catch(function () { /* individual loaders already handle their errors */ })
      .then(function () {
        if (activeSymbol) return loadPanel(activeSymbol);
      })
      .then(function () {
        setLoading(false);
        setUpdated(ts);
      });
  }

  // ===========================================================================
  // BOOT
  // ===========================================================================
  function boot() {
    // Page guard: app.js's overview-specific boot only runs on index.html.
    // Other pages have their own <page>.js and would crash on missing
    // elements (#symbols-body etc.), bringing down window.FA.ui before
    // dependent modules (admin.js, settings.js) get a chance to use it.
    if (!document.getElementById('symbols-body')) return;

    // Placeholders for sections whose endpoints aren't wired yet.
    renderPortfolioSkeleton();
    renderAlertsSkeleton();
    renderMarketSkeleton();

    // Kick off the data loop. Keep the handles so we can clearInterval
    // them on pagehide — otherwise navigating away from /index leaks a
    // pair of long-running fetch loops that hammer /api/health and
    // /api/v1/decisions/recent even after the page is gone.
    pollHealth();
    refreshAll();
    var healthTimer = setInterval(pollHealth, HEALTH_MS);
    var refreshTimer = setInterval(refreshAll,  REFRESH_MS);
    window.addEventListener("pagehide", function () {
      clearInterval(healthTimer);
      clearInterval(refreshTimer);
    });
    // `connectWs` is defined later in this file inside a separate IIFE
    // (lines ~1167+). From `boot()`'s lexical scope it is undefined —
    // calling the bare name throws ReferenceError on every page load.
    // Use the no-op shim provided by ui.js, OR the real one that
    // IIFE #2 wires onto window.FA.connectWs at the end of this file.
    if (window.FA && typeof window.FA.connectWs === 'function') {
      window.FA.connectWs();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // ==========================================================================
  // Shared helpers — exposed on window.FA for the per-page scripts
  // (decisions.js, decision-detail.js). Additive: the home-page logic above
  // keeps working unchanged. Anything below is safe to call from any page.
  // ==========================================================================
  var FA = {
    API_BASE: API_BASE,

    /** Escape a value for safe insertion into innerHTML. */
    esc: escapeHtml,

    /** Format a number with a fixed digit count. */
    fmtNum: fmtNum,

    /** Format a volume (K/M/B suffix). */
    fmtVol: fmtVol,

    /** HH:MM:SS in tr-TR locale. */
    fmtTime: fmtTime,

    /** Format ₺ with Turkish thousands separator. */
    fmtTRY: fmtTRY,

    /** Format percentage change as { text, cls, sign }. */
    fmtPct: fmtPct,

    /** JSON GET helper. */
    fetchJson: fetchJson,

    /** Accept an array OR an envelope {items:[]} / {decisions:[]} / etc. */
    normalizeList: normalizeList,

    /**
     * Short decision id — first 8 chars of the UUID (dashes stripped).
     * Used in tables, badges, link hrefs.
     */
    shortId: function (id) {
      if (!id) return '';
      return String(id).replace(/-/g, '').slice(0, 8);
    },

    /** Detail page URL for a decision (works from any path). */
    detailUrl: function (id) {
      return 'decision-detail?id=' + encodeURIComponent(id);
    },

    /** Decisions list page URL with optional ticker pre-filter. */
    decisionsUrl: function (ticker) {
      return ticker ? ('decisions?ticker=' + encodeURIComponent(ticker)) : 'decisions';
    },

    /**
     * Read a query-string parameter off the current URL. Returns null if
     * the parameter is absent (matches URLSearchParams.get semantics).
     */
    getQueryParam: function (name) {
      try {
        var s = window.location.search || '';
        if (!s || s.charAt(0) !== '?') return null;
        var raw = s.slice(1);
        var parts = raw.split('&');
        for (var i = 0; i < parts.length; i++) {
          if (!parts[i]) continue;
          var eq = parts[i].indexOf('=');
          var k = eq >= 0 ? parts[i].slice(0, eq) : parts[i];
          var v = eq >= 0 ? parts[i].slice(eq + 1) : '';
          if (decodeURIComponent(k) === name) {
            return decodeURIComponent(v.replace(/\+/g, ' '));
          }
        }
      } catch (e) { /* fall through */ }
      return null;
    },

    /**
     * Render an ISO timestamp as Turkish-local datetime:
     *   "24 Eylül 2026 14:30"
     * Falls back to the raw string if parsing fails.
     */
    renderTRT: function (iso) {
      if (!iso) return '—';
      var d = (typeof iso === 'string') ? new Date(iso) : (iso instanceof Date ? iso : null);
      if (!d || isNaN(d.getTime())) return String(iso);
      try {
        var months = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran',
                      'Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
        var dd = d.getDate();
        var mm = months[d.getMonth()];
        var yy = d.getFullYear();
        var hh = (d.getHours() < 10 ? '0' : '') + d.getHours();
        var mi = (d.getMinutes() < 10 ? '0' : '') + d.getMinutes();
        return dd + ' ' + mm + ' ' + yy + ' ' + hh + ':' + mi;
      } catch (e) { return String(iso); }
    },

    /**
     * Vertical confidence meter — accepts 0..1 OR 0..100.
     * Returns <div class="confidence-meter"><div class="bar" style="height: N%"/></div>.
     * Colour is set inline via --confidence-color (CSS picks up the var).
     */
    renderConfidenceMeter: function (value) {
      var n = (value === null || value === undefined || isNaN(Number(value))) ? 0 : Number(value);
      var pct = n > 1 ? Math.max(0, Math.min(100, n)) : Math.max(0, Math.min(100, n * 100));
      var color = pct >= 70 ? 'var(--accent)'
                : pct >= 40 ? 'var(--warn)'
                : 'var(--danger)';
      return ''
        + '<div class="confidence-meter" title="' + pct.toFixed(0) + '%" '
        + 'role="meter" aria-valuenow="' + pct.toFixed(0) + '" '
        + 'aria-valuemin="0" aria-valuemax="100" '
        + 'aria-label="confidence ' + pct.toFixed(0) + ' percent">'
        +   '<div class="bar" style="height:' + pct.toFixed(0) + '%; --confidence-color:' + color + '"></div>'
        +   '<span class="value">' + pct.toFixed(0) + '%</span>'
        + '</div>';
    },

    /**
     * Action badge. Accepts BUY | SELL | HOLD | REDUCE | INSUFFICIENT_EVIDENCE.
     * Returns <span class="badge action-buy">BUY</span>.
     */
    renderActionBadge: function (action) {
      var raw = (action === null || action === undefined) ? '' : String(action);
      var lower = raw.toLowerCase();
      // INSUFFICIENT_EVIDENCE -> "insufficient" keeps the CSS class short.
      var cls = lower === 'insufficient_evidence' ? 'insufficient' : lower;
      return '<span class="badge action-' + this.esc(cls) + '">' + this.esc(raw || '—') + '</span>';
    },

    /**
     * Compliance status badge. PENDING | APPROVED | BLOCKED | REVIEW | FLAGGED.
     * Unknown values fall back to a neutral badge.
     */
    renderComplianceBadge: function (status) {
      var raw = (status === null || status === undefined) ? '' : String(status);
      var lower = raw.toLowerCase();
      var cls = (lower === 'approved' || lower === 'review' || lower === 'flagged'
              || lower === 'blocked'  || lower === 'pending')
        ? lower : 'unknown';
      return '<span class="badge compliance-' + cls + '">' + this.esc(raw || '—') + '</span>';
    },

    /**
     * Evidence card. Accepts one element of decision.evidence[] OR an object
     * with the same shape. Renders a collapsible <details> card.
     */
    renderEvidenceCard: function (evidence) {
      if (!evidence || typeof evidence !== 'object') {
        return '<article class="evidence-card empty"><div class="evidence-body">—</div></article>';
      }
      var stream   = evidence.stream || evidence.source || 'evidence';
      var signal   = (evidence.signal || 'NEUTRAL').toString().toUpperCase();
      var strength = Number(evidence.strength);
      var conf     = Number(evidence.confidence);
      var sourceId = evidence.source_id || evidence.sourceId || '—';
      var retrieved= evidence.retrieved_at || evidence.retrievedAt || null;
      var meta     = evidence.metadata || {};
      var dirCls = signal === 'BULLISH' ? 'pos'
                 : signal === 'BEARISH' ? 'neg'
                 : 'neutral';
      var metaHtml = '';
      if (meta && typeof meta === 'object' && !Array.isArray(meta)) {
        var keys = Object.keys(meta);
        if (keys.length) {
          metaHtml = '<dl class="evidence-meta">'
            + keys.map(function (k) {
                var v = meta[k];
                if (v === null || v === undefined) v = '—';
                if (typeof v === 'object') v = JSON.stringify(v);
                return '<dt>' + this.esc(k) + '</dt><dd>' + this.esc(String(v)) + '</dd>';
              }.bind(this)).join('')
            + '</dl>';
        }
      }
      return ''
        + '<article class="evidence-card">'
        +   '<details>'
        +     '<summary>'
        +       '<span class="evidence-stream">' + this.esc(stream) + '</span>'
        +       '<span class="evidence-signal ' + dirCls + '">' + this.esc(signal) + '</span>'
        +       '<span class="evidence-strength-label">güç / strength</span>'
        +       this.renderConfidenceMeter(isNaN(strength) ? 0 : strength)
        +       '<span class="evidence-confidence-label">güvenilirlik / confidence</span>'
        +       this.renderConfidenceMeter(isNaN(conf) ? 0 : conf)
        +     '</summary>'
        +     '<div class="evidence-body">'
        +       '<p class="evidence-source"><span>Kaynak / Source</span> <code>' + this.esc(sourceId) + '</code></p>'
        +       (retrieved ? '<p class="evidence-retrieved"><span>Alınma zamanı / Retrieved at</span> '
        +         + this.esc(this.renderTRT(retrieved)) + '</p>' : '')
        +       metaHtml
        +     '</div>'
        +   '</details>'
        + '</article>';
    },

    /**
     * Generic table builder.
     *   headers: [{label, cls?}]
     *   rows:    [[htmlCell, ...], ...]
     * Returns a <table class="data-table">…</table> string.
     */
    renderTable: function (headers, rows) {
      var head = '<thead><tr>'
        + headers.map(function (h) {
            return '<th' + (h && h.cls ? ' class="' + this.esc(h.cls) + '"' : '') + '>'
                 + this.esc(h && h.label ? h.label : '') + '</th>';
          }.bind(this)).join('')
        + '</tr></thead>';
      var body;
      if (!rows || rows.length === 0) {
        body = '<tbody><tr><td class="empty-state" colspan="' + headers.length + '">'
             + 'Henüz kayıt yok / No records yet'
             + '</td></tr></tbody>';
      } else {
        body = '<tbody>' + rows.map(function (r) {
          return '<tr>' + r.map(function (cell) { return '<td>' + cell + '</td>'; }).join('') + '</tr>';
        }).join('') + '</tbody>';
      }
      return '<div class="table-wrap"><table class="data-table">' + head + body + '</div>';
    },

    /**
     * Force the current page to reload with `?_ts=…` so the browser drops cache.
     * Used by the manual "refresh" button.
     */
    hardRefresh: function () {
      try {
        var u = new URL(window.location.href);
        u.searchParams.set('_ts', Date.now().toString());
        window.location.replace(u.toString());
      } catch (e) { window.location.reload(); }
    },

    /**
     * Set up a polling loop on `fn()`. The fn must return a Promise (or undefined).
     * Cancels on pagehide.
     */
    attachRefreshLoop: function (fn, intervalMs) {
      var ms = intervalMs || 30000;
      var run = function () {
        Promise.resolve(fn()).catch(function () { /* page handles errors */ });
      };
      run();
      var h = setInterval(run, ms);
      window.addEventListener('pagehide', function () { clearInterval(h); });
      return h;
    },

    /**
     * Parse a jsonb value that api-gateway returns as a JSON-encoded string
     * (asyncpg serialises jsonb as TEXT on the way out). Falls back to the
     * original value if it's already an object or unparseable.
     */
    parseJsonb: function (v) {
      if (v === null || v === undefined) return null;
      if (typeof v === 'object') return v;
      if (typeof v !== 'string') return v;
      var s = v.trim();
      if (!s || s === 'null' || s === 'undefined') return null;
      if (s.charAt(0) !== '{' && s.charAt(0) !== '[') return null;
      try { return JSON.parse(s); } catch (e) { return null; }
    },

    /** Toggle the home-page refresh indicator (if present in the DOM). */
    setLoading: setLoading,
  };

  // Expose globally for the per-page scripts (decisions.js, decision-detail.js).
  // Existing index-page behaviour is fully untouched.
  // Merge into window.FA (rather than overwriting) so the namespaces created
  // by ui.js (window.FA.toast.show, window.FA.api.fetchJSON) and
  // side-nav.js (window.FA.sideNav.mount) survive. Older code paths that
  // expect FA.api.fetchJson / FA.ui.fetchAdmin still resolve.
  window.FA = window.FA || {};
  Object.assign(window.FA, FA);
})();

/* ============================================================================
 * 3D GLASSMORPHISM ADD-ON — Theme + Tilt-on-Hover + Admin Token helpers
 * Kept in a separate IIFE so the original `FA` module stays untouched.
 * Exposed as window.FA.ui (theme, toast, tilt, admin token).
 * =========================================================================== */
(function () {
  'use strict';

  var THEME_KEY     = 'finance-ai.theme';
  var ADMIN_KEY_KEY = 'finance-ai.admin_token';

  // Sun + Moon SVGs reused by every theme toggle.
  var SUN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
  var MOON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

  /** Read the saved theme preference; falls back to system, then 'dark'. */
  function readSavedTheme() {
    try {
      var v = localStorage.getItem(THEME_KEY);
      if (v === 'light' || v === 'dark') return v;
    } catch (e) {}
    try {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        return 'light';
      }
    } catch (e) {}
    return 'dark';
  }

  /** Apply a theme ('light' | 'dark') to <html> and update toggle buttons. */
  function applyTheme(theme) {
    var t = (theme === 'light') ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', t);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      var sun = btn.querySelector('[data-theme-icon="light"]');
      var moon = btn.querySelector('[data-theme-icon="dark"]');
      if (sun) sun.classList.toggle('is-active', t === 'light');
      if (moon) moon.classList.toggle('is-active', t === 'dark');
      btn.setAttribute('aria-pressed', t === 'light' ? 'false' : 'true');
      btn.setAttribute('title', t === 'light'
        ? 'Aydınlık mod / Light mode (tıklayın → karanlık)'
        : 'Karanlık mod / Dark mode (tıklayın → aydınlık)');
    });
    // Update admin-link lock state.
    document.querySelectorAll('[data-admin-link]').forEach(function (a) {
      var has = !!getAdminToken();
      a.classList.toggle('is-locked', !has);
    });
    try { document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: t } })); } catch (e) {}
  }

  /** Flip the theme and persist. */
  function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme') || 'dark';
    var next = current === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    applyTheme(next);
    return next;
  }

  /** Wire up the theme toggle button (creates one if missing) and bind clicks. */
  function initThemeToggle() {
    applyTheme(readSavedTheme());
    // Auto-create a toggle if a placeholder exists but no button yet.
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      if (!btn.querySelector('[data-theme-icon]')) {
        btn.innerHTML =
          '<span class="theme-toggle-icon" data-theme-icon="light" aria-hidden="true">' + SUN_SVG + '</span>' +
          '<span class="theme-toggle-icon" data-theme-icon="dark"  aria-hidden="true">' + MOON_SVG + '</span>';
      }
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        toggleTheme();
      });
    });
    // React to OS changes only when the user has NOT set a manual preference.
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var handler = function (ev) {
        try {
          if (localStorage.getItem(THEME_KEY)) return;
        } catch (e) {}
        applyTheme(ev.matches ? 'dark' : 'light');
      };
      if (mq.addEventListener) mq.addEventListener('change', handler);
      else if (mq.addListener) mq.addListener(handler);
    }
  }

  // ---- Admin token helpers ------------------------------------------------
  function getAdminToken() {
    try {
      var v = localStorage.getItem(ADMIN_KEY_KEY);
      return v && v.trim() ? v.trim() : '';
    } catch (e) { return ''; }
  }
  function setAdminToken(v) {
    try {
      if (v && v.trim()) localStorage.setItem(ADMIN_KEY_KEY, v.trim());
      else localStorage.removeItem(ADMIN_KEY_KEY);
    } catch (e) {}
    document.querySelectorAll('[data-admin-link]').forEach(function (a) {
      a.classList.toggle('is-locked', !getAdminToken());
    });
  }

  /**
   * Wrap fetch so every /api/* call automatically carries the admin token
   * when present. Non-admin endpoints (e.g. /v1/market/*, /health/*) are not
   * affected by default — opt in by passing { admin: true }.
   */
  function fetchAdmin(path, opts) {
    opts = opts || {};
    var headers = Object.assign({}, opts.headers || {});
    var token = getAdminToken();
    if (token) headers['X-Admin-Token'] = token;
    return fetch(path, Object.assign({}, opts, { headers: headers }));
  }

  // ---- Tilt-on-hover for glass cards --------------------------------------
  /** Attach mousemove tilt listeners to every .glass / .card element. */
  function initTilt() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var MAX_TILT = 4; // degrees
    var els = document.querySelectorAll('.glass, .card');
    els.forEach(function (el) {
      if (el.dataset.tiltBound === '1') return;
      el.dataset.tiltBound = '1';
      el.addEventListener('mousemove', function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width;
        var py = (e.clientY - r.top) / r.height;
        var rx = (0.5 - py) * MAX_TILT; // tilt toward top → rotateX negative
        var ry = (px - 0.5) * MAX_TILT;
        el.style.transform =
          'perspective(var(--perspective)) translateZ(0) ' +
          'rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg) translateY(-2px)';
      });
      el.addEventListener('mouseleave', function () {
        el.style.transform = '';
      });
    });
  }

  // ---- Init on DOMContentLoaded -------------------------------------------
  // Theme toggling now lives in side-nav.js (own the toggle button); here
  // we keep tilt + admin link lock.
  function boot() {
    initTilt();
    document.querySelectorAll('[data-admin-link]').forEach(function (a) {
      a.classList.toggle('is-locked', !getAdminToken());
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // Public surface (extend, don't replace).
  // Note: `toast` is intentionally absent — ui.js's `FA.toast.show` / `FA.ui.toast`
  // (a 1-arg shim around showToast) is the canonical surface for every page.
  window.FA = window.FA || {};
  window.FA.ui = {
    applyTheme:      applyTheme,
    toggleTheme:     toggleTheme,
    getTheme:        function () { return document.documentElement.getAttribute('data-theme') || 'dark'; },
    getAdminToken:   getAdminToken,
    setAdminToken:   setAdminToken,
    fetchAdmin:      fetchAdmin,
    initTilt:        initTilt,
    SUN_SVG:         SUN_SVG,
    MOON_SVG:        MOON_SVG,
  };

  // Convenience global.
  window.toggleTheme = toggleTheme;

  // ---- WebSocket live tick (issue #1 / FR-005) ------------------------------
  var _ws = null;
  var _wsAttempts = 0;
  // Close the WS and reset state on navigation so we don't leave the
  // reconnect timer + a half-open socket firing after the user leaves
  // the page. Without this the user navigates to /decisions and the
  // ws_market connection (and its exponential-backoff setTimeout
  // chain) keeps running indefinitely — real memory + socket leak.
  window.addEventListener("pagehide", function () {
    _wsAttempts = 0;
    if (_ws && _ws.readyState !== WebSocket.CLOSED) {
      try { _ws.close(); } catch (e) { /* already closed */ }
    }
    _ws = null;
  });
  var _wsToken = null;

  function ensureWsToken(cb) {
    if (_wsToken) { cb(_wsToken); return; }
    try {
      var cached = localStorage.getItem('finance-ai.ws_token');
      var expiry = parseInt(localStorage.getItem('finance-ai.ws_token_exp') || '0', 10);
      if (cached && expiry && Date.now() / 1000 < expiry - 60) {
        _wsToken = cached;
        cb(cached);
        return;
      }
    } catch (e) { /* ignore */ }
    // Fetch a fresh dev-token from the api-gateway.
    fetch('/api/v1/auth/dev-token', { method: 'POST',
        headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (data && data.access_token) {
          _wsToken = data.access_token;
          try {
            localStorage.setItem('finance-ai.ws_token', _wsToken);
            localStorage.setItem('finance-ai.ws_token_exp',
              String(Math.floor(Date.now() / 1000) + (data.expires_in || 3600)));
          } catch (e) { /* ignore */ }
          cb(_wsToken);
        } else {
          cb(null);  // dev-token endpoint disabled — connect without auth
        }
      })
      .catch(function () { cb(null); });
  }

  function connectWs() {
    ensureWsToken(function (token) {
      try {
        var proto = (location.protocol === 'https:') ? 'wss:' : 'ws:';
        var url = proto + '//' + (location.host || 'localhost:8080') +
                  '/api/v1/market/ws/market';
        if (token) url += '?token=' + encodeURIComponent(token);
        if (_ws && _ws.readyState !== WebSocket.CLOSED) {
          try { _ws.close(); } catch (e) { /* already closed */ }
        }
        _ws = new WebSocket(url);
        _ws.onmessage = function (ev) {
          try {
            var msg = JSON.parse(ev.data);
            if (msg && msg.ticker && typeof msg.last === 'number') {
              liveTicks[msg.ticker] = msg;
              flashTickerCell(msg.ticker);
            }
          } catch (e) { /* ignore */ }
        };
        _ws.onopen = function () { _wsAttempts = 0; };
        _ws.onerror = function () { /* let onclose handle retry */ };
        _ws.onclose = function (ev) {
          // 1008 = policy violation (auth failed). Clear cached token and retry
          // after a backoff so we can fetch a fresh one.
          if (ev && ev.code === 1008) {
            _wsToken = null;
            try {
              localStorage.removeItem('finance-ai.ws_token');
              localStorage.removeItem('finance-ai.ws_token_exp');
            } catch (e) { /* ignore */ }
          }
          _wsAttempts++;
          var delay = Math.min(30000, 1000 * Math.pow(2, _wsAttempts));
          setTimeout(connectWs, delay);
        };
      } catch (e) { /* websocket unavailable */ }
    });
  }

  // Expose the real WS connect onto window.FA so the boot() call in IIFE #1
  // (and any future caller) reaches the live implementation rather than the
  // ui.js no-op shim. Overrides the shim because we loaded after ui.js.
  window.FA = window.FA || {};
  window.FA.connectWs = connectWs;

  // Most-recent tick per ticker; merged into the next refreshAll() render.
  var liveTicks = {};
  function flashTickerCell(ticker) {
    try {
      var cell = document.querySelector('[data-ticker="' + ticker + '"] .live-dot');
      if (!cell) return;
      cell.classList.remove('flash');
      void cell.offsetWidth;  // restart animation
      cell.classList.add('flash');
    } catch (e) { /* ignore */ }
  }

  // ---- Toast system (ui-ux-polish-2026) -------------------------------------
  function ensureToastContainer() {
    var el = document.querySelector('.toast-container');
    if (el) return el;
    el = document.createElement('div');
    el.className = 'toast-container';
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-atomic', 'true');
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

  // Expose for other modules.
  window.FA = window.FA || {};
  window.FA.ui = window.FA.ui || {};
  window.FA.ui.toast = toast;

  // ---- Skip-to-main link ---------------------------------------------------
  (function addSkipLink() {
    if (document.querySelector('.skip-link')) return;
    var a = document.createElement('a');
    a.className = 'skip-link';
    a.href = '#main';
    a.textContent = 'İçeriğe atla / Skip to content';
    document.body.insertBefore(a, document.body.firstChild);
  })();

  // ---- Command bar (Cmd+K / Ctrl+K) ----------------------------------------
  var CMD_ACTIONS = [
    { label: 'Genel Bakış / Overview', href: '/', hint: 'G O' },
    { label: 'Kararlar / Decisions', href: '/decisions', hint: 'G D' },
    { label: 'Portföy / Portfolio', href: '/portfolio', hint: 'G P' },
    { label: 'Uyarılar / Alerts', href: '/alerts', hint: 'G A' },
    { label: 'Sistem Sağlığı / System Health', href: '/system-health', hint: 'G S' },
    { label: 'Admin', href: '/admin', hint: 'G .' },
    { label: 'Ayarlar / Settings', href: '/settings', hint: 'G ,' },
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
        li.addEventListener('click', function () {
          window.location.href = a.href;
        });
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

  // ---- Keyboard shortcuts --------------------------------------------------
  var _gArmed = false;
  var _gArmedAt = 0;
  document.addEventListener('keydown', function (e) {
    // Cmd+K / Ctrl+K — command bar
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openCommandBar();
      return;
    }
    // Skip when typing in inputs.
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) {
      return;
    }
    // G then <letter> navigation.
    if (e.key.toLowerCase() === 'g' && !_gArmed) {
      _gArmed = true;
      _gArmedAt = Date.now();
      setTimeout(function () { _gArmed = false; }, 1500);
      return;
    }
    if (_gArmed && Date.now() - _gArmedAt < 1500) {
      var map = {
        'o': '/', 'd': '/decisions', 'p': '/portfolio',
        'a': '/alerts', 's': '/system-health',
        ',': '/settings', '.': '/admin',
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