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

  /** GET → text (cheap reachability check). */
  function fetchText(path) {
    return fetch(path, { method: 'GET', credentials: 'same-origin' });
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

    host.innerHTML = ''
      + '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" '
      +     'role="img" aria-label="' + escapeHtml(symbol) + ' sparkline" '
      +     'style="width:100%;height:100%;">'
      +   '<path d="' + areaPath + '" fill="' + fill + '" fill-opacity="' + (intensity * 0.35).toFixed(3) + '" stroke="none"/>'
      +   '<path d="' + linePath + '" fill="none" stroke="' + stroke + '" stroke-width="1.4" '
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
      var p = pctSign(t.change);
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

  function pctSign(n) {
    return { change: n };
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
    // Placeholders for sections whose endpoints aren't wired yet.
    renderPortfolioSkeleton();
    renderAlertsSkeleton();
    renderMarketSkeleton();

    // Kick off the data loop.
    pollHealth();
    refreshAll();
    setInterval(pollHealth, HEALTH_MS);
    setInterval(refreshAll,  REFRESH_MS);
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

    /** POST helper (unused for now; wired for future actions). */
    fetchPost: function (path, body) {
      return fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body || {}),
      }).then(function (res) {
        if (!res.ok) {
          var err = new Error('HTTP ' + res.status + ' on POST ' + path);
          err.status = res.status;
          throw err;
        }
        return res.json();
      });
    },

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
      return 'decision-detail.html?id=' + encodeURIComponent(id);
    },

    /** Decisions list page URL with optional ticker pre-filter. */
    decisionsUrl: function (ticker) {
      return ticker ? ('decisions.html?ticker=' + encodeURIComponent(ticker)) : 'decisions.html';
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
  window.FA = FA;
})();