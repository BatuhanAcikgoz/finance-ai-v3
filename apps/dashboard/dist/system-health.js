/* ===========================================================================
 * System health page — vanilla JS
 *   - /api/health for overall service readiness
 *   - /api/v1/agents for per-worker statuses (mocked if missing)
 *   - /api/v1/events for activity feed (mocked if missing)
 *   - LLM cost card and queue depth fall back to '—' until metrics are wired.
 * Auto-refresh every 10s. All values safely degrade to placeholders.
 * ========================================================================= */
(function () {
  'use strict';

  var API_BASE = '/api';
  var REFRESH_MS = 10000;

  // Canonical worker list per spec.
  var WORKERS = [
    { id: 'api-gateway',         label: 'api-gateway',         hint: 'gateway' },
    { id: 'postgres',            label: 'postgres',            hint: 'db' },
    { id: 'redis',               label: 'redis',               hint: 'cache' },
    { id: 'qdrant',              label: 'qdrant',              hint: 'vector' },
    { id: 'kap-collector',       label: 'kap-collector',       hint: 'feed' },
    { id: 'technical-analysis',  label: 'technical-analysis',  hint: 'agent' },
    { id: 'decision-engine',     label: 'decision-engine',     hint: 'agent' },
    { id: 'report-generator',    label: 'report-generator',    hint: 'agent' },
  ];

  // Synthetic fallback data so the page renders something coherent in dev.
  var SYNTH_AGENTS = [
    { id: 'api-gateway',        status: 'ok',       latency_ms:   14, last_seen: 0 },
    { id: 'postgres',           status: 'ok',       latency_ms:    3, last_seen: 0 },
    { id: 'redis',              status: 'ok',       latency_ms:    1, last_seen: 0 },
    { id: 'qdrant',             status: 'degraded', latency_ms:  182, last_seen: 12, last_log: 'WARN shard rebalance: 1 pending' },
    { id: 'kap-collector',      status: 'ok',       latency_ms:   48, last_seen: 4,  last_log: 'INFO pulled 84 disclosures' },
    { id: 'technical-analysis', status: 'ok',       latency_ms:  340, last_seen: 22, last_log: 'INFO computed 48 indicator sets' },
    { id: 'decision-engine',    status: 'ok',       latency_ms: 1240, last_seen: 5,  last_log: 'INFO committed 6 decisions to portfolio default' },
    { id: 'report-generator',   status: 'down',     latency_ms: null, last_seen: 1840, last_log: 'ERROR upstream worker offline (no LLM keys)' },
  ];
  var SYNTH_EVENTS = [
    { ts: '08:14:22', src: 'risk-engine',  msg: 'THYAO weight exceeds drift limit (18.4% vs 18.0%)' },
    { ts: '07:55:01', src: 'kap-collector', msg: 'Backlog draining, 4,820 → 220 in 6 min' },
    { ts: '07:31:45', src: 'supervisor',    msg: 'LLM cost day total now $42.18 / $50 budget' },
    { ts: '06:12:09', src: 'postgres',      msg: 'replica-2 self-recovered after 47s lag' },
    { ts: '05:42:31', src: 'decision-engine', msg: 'BIST tick received; 48 symbols resumed' },
    { ts: '04:01:00', src: 'cron',          msg: 'nightly fundamentals job completed (12 issuers)' },
    { ts: '02:33:11', src: 'report-generator', msg: '2026-09-23.pdf generated and stored' },
    { ts: '01:15:48', src: 'qdrant',        msg: 'decisions_v3 upserted with 4 new vectors' },
  ];

  // ---- DOM refs -------------------------------------------------------------
  var $grid          = document.getElementById('workers-grid');
  var $events        = document.getElementById('events-list');
  var $refreshInd    = document.getElementById('refresh-indicator');
  var $refreshText   = document.getElementById('refresh-text');
  var $overallPill   = document.getElementById('overall-pill');
  var $overallText   = document.getElementById('overall-text');
  var $overallProbe  = document.getElementById('overall-probe');
  var $llmToday      = document.getElementById('llm-today');
  var $llmPer        = document.getElementById('llm-per-decision');
  var $llmCount      = document.getElementById('llm-dec-count');
  var $qKap          = document.getElementById('q-kap');
  var $qDec          = document.getElementById('q-dec');
  var $qRep          = document.getElementById('q-rep');
  var $qBarKap       = document.getElementById('q-bar-kap');
  var $qBarDec       = document.getElementById('q-bar-dec');
  var $qBarRep       = document.getElementById('q-bar-rep');
  var $qBarKapPct    = document.getElementById('q-bar-kap-pct');
  var $qBarDecPct    = document.getElementById('q-bar-dec-pct');
  var $qBarRepPct    = document.getElementById('q-bar-rep-pct');
  var $lastUpd       = document.getElementById('last-updated');

  // ---- Helpers --------------------------------------------------------------
  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fmtTime(d) {
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  function fmtAgo(seconds) {
    if (seconds === null || seconds === undefined) return 'never';
    if (seconds < 60)        return seconds + ' sn / s ago';
    if (seconds < 3600)      return Math.floor(seconds / 60)   + ' dk / min ago';
    if (seconds < 86400)     return Math.floor(seconds / 3600) + ' sa / h ago';
    return Math.floor(seconds / 86400) + ' gün / d ago';
  }
  function fmtUsd(n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtInt(n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return Number(n).toLocaleString('en-US');
  }
  function setLoading(b) {
    if (b) { $refreshInd.classList.add('is-loading'); $refreshText.textContent = 'yenileniyor / refreshing…'; }
    else   { $refreshInd.classList.remove('is-loading'); $refreshText.textContent = 'idle'; }
  }
  function safeFetch(path) {
    return fetch(API_BASE + path, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  // ---- Data fetch -----------------------------------------------------------
  function fetchAll() {
    setLoading(true);
    var promises = {
      health:  safeFetch('/health'),
      agents:  safeFetch('/v1/agents'),
      events:  safeFetch('/v1/events'),
      cost:    safeFetch('/v1/metrics/llm-cost/today'),
      queues:  safeFetch('/v1/metrics/queues'),
    };
    return Promise.all(Object.values(promises)).then(function (vals) {
      var keys = Object.keys(promises);
      var out = {};
      keys.forEach(function (k, i) { out[k] = vals[i]; });
      return out;
    });
  }

  // ---- Normalisation --------------------------------------------------------
  function normaliseAgents(data) {
    var arr = (data && (data.agents || data.items || data.workers || data)) || null;
    if (!Array.isArray(arr) || !arr.length) return null;
    return arr.map(function (a) {
      return {
        id: a.id || a.name || a.component || '',
        status: (a.status || a.state || a.health || '').toLowerCase(),
        latency_ms: (typeof a.latency_ms === 'number') ? a.latency_ms : (a.latency || null),
        last_seen: (typeof a.last_seen === 'number') ? a.last_seen : (a.last_seen_seconds || null),
        last_log: a.last_log || a.recent_log || '',
      };
    });
  }

  function normaliseEvents(data) {
    var arr = (data && (data.events || data.items || data.recent || data)) || null;
    if (!Array.isArray(arr) || !arr.length) return null;
    return arr.slice(0, 20).map(function (e) {
      return {
        ts: e.ts || e.time || e.timestamp || '',
        src: e.source || e.agent || e.component || 'system',
        msg: e.message || e.title || e.summary || '',
      };
    });
  }

  // ---- Rendering ------------------------------------------------------------
  function renderOverall(health) {
    var status = (health && (health.status || health.state)) || '';
    status = (status + '').toLowerCase();
    var pillCls = '', text = 'bilinmiyor / unknown';
    if (status === 'healthy' || status === 'ready' || status === 'ok' || status === 'alive') {
      pillCls = 'ok'; text = 'sağlıklı / healthy';
    } else if (status === 'degraded') {
      pillCls = 'degraded'; text = 'kısıtlı / degraded';
    } else if (status === 'down' || status === 'unhealthy') {
      pillCls = 'down'; text = 'çöktü / down';
    }
    $overallPill.className = 'pill ' + pillCls;
    $overallText.textContent = text;
    $overallProbe.textContent = health ? fmtTime(new Date()) : '— api ulaşılamıyor / api unreachable';
  }

  function renderWorkers(synthAgents /* when no api */, realAgents, nowSec) {
    var list;
    if (realAgents && realAgents.length) {
      // Merge real agents over the canonical worker list; unknowns marked 'unknown'.
      var byId = {};
      realAgents.forEach(function (r) { byId[r.id] = r; });
      list = WORKERS.map(function (w) {
        var r = byId[w.id];
        return r ? Object.assign({}, w, r) : Object.assign({}, w, { status: 'unknown' });
      });
    } else {
      list = WORKERS.map(function (w) {
        var s = (synthAgents || []).find(function (x) { return x.id === w.id; });
        if (!s) return Object.assign({}, w, { status: 'unknown' });
        return Object.assign({}, w, s);
      });
    }
    var html = list.map(function (w) {
      var pipCls = (w.status === 'ok') ? 'ok'
        : (w.status === 'degraded') ? 'degraded'
        : (w.status === 'down') ? 'down' : 'unknown';
      var latBadge = '';
      if (w.status === 'down') {
        latBadge = '<span class="badge down">erişilemez / unreachable</span>';
      } else if (typeof w.latency_ms === 'number') {
        var latCls = w.latency_ms < 500 ? 'ok' : (w.latency_ms < 1500 ? 'slow' : '');
        var latTxt = w.latency_ms < 1000
          ? w.latency_ms + ' ms'
          : (w.latency_ms / 1000).toFixed(2) + ' sn / s';
        latBadge = '<span class="badge ' + latCls + '">' + latTxt + '</span>';
      } else {
        latBadge = '<span class="badge">— ms</span>';
      }
      var ago = (typeof w.last_seen === 'number') ? fmtAgo(w.last_seen + nowSec) : '—';
      var logTail = w.last_log ? '<span style="display:block; margin-top:4px; font-size:11px; color:var(--muted); font-family: ui-monospace, Menlo, monospace;">› ' + escapeHtml(w.last_log) + '</span>' : '';
      return '' +
        '<div class="worker" data-id="' + escapeHtml(w.id) + '">' +
          '<div class="name"><span>' + escapeHtml(w.label) + '</span><span class="pip ' + pipCls + '" title="' + escapeHtml(w.status || 'unknown') + '"></span></div>' +
          '<div class="meta">' + latBadge + '<span>' + ago + '</span></div>' +
          logTail +
        '</div>';
    }).join('');
    $grid.innerHTML = html;
  }

  function renderEvents(synthEvents, realEvents) {
    var list = realEvents && realEvents.length ? realEvents : (synthEvents || []);
    if (!list.length) {
      $events.innerHTML = '<li class="empty-state" style="grid-column: 1 / -1;">Etkinlik yok / No recent events.</li>';
      return;
    }
    $events.innerHTML = list.map(function (e) {
      return '' +
        '<li>' +
          '<span class="ts">' + escapeHtml(e.ts || '—') + '</span>' +
          '<span class="src">' + escapeHtml(e.src || e.source || 'system') + '</span>' +
          '<span class="msg">' + escapeHtml(e.msg || e.message || '—') + '</span>' +
        '</li>';
    }).join('');
  }

  function renderLlm(cost) {
    if (!cost || typeof cost !== 'object') {
      $llmToday.textContent = '—';
      $llmPer.textContent = '—';
      $llmCount.textContent = '—';
      return;
    }
    $llmToday.textContent = fmtUsd(cost.total_today_usd);
    $llmPer.textContent   = fmtUsd(cost.per_decision_usd);
    $llmCount.textContent = fmtInt(cost.decisions_today);
  }

  function renderQueues(queues) {
    var cap = 10000;
    function setValue(el, numEl, barEl, barPctEl) {
      if (!queues || typeof queues[numEl] === 'undefined') {
        el.textContent = '—'; barEl.style.width = '0%'; barPctEl.textContent = '—';
      } else {
        var n = Number(queues[numEl]);
        el.textContent = fmtInt(n);
        var pct = Math.min(100, Math.round((n / cap) * 100));
        barEl.style.width = pct + '%';
        barEl.classList.remove('warn', 'danger');
        if (pct >= 70) barEl.classList.add('danger');
        else if (pct >= 40) barEl.classList.add('warn');
        barPctEl.textContent = pct + '%';
      }
    }
    setValue($qKap, 'kap_collector',       $qBarKap, $qBarKapPct);
    setValue($qDec, 'decision_engine',    $qBarDec, $qBarDecPct);
    setValue($qRep, 'report_generator',   $qBarRep, $qBarRepPct);
  }

  // ---- Bootstrap ------------------------------------------------------------
  function refresh() {
    fetchAll().then(function (data) {
      renderOverall(data.health);
      // Synth agents get a slowly ticking "last_seen" so the UI feels live.
      var nowSec = 0;
      renderWorkers(SYNTH_AGENTS, normaliseAgents(data.agents), nowSec);
      renderEvents(SYNTH_EVENTS, normaliseEvents(data.events));
      renderLlm(data.cost);
      renderQueues(data.queues);
      $lastUpd.textContent = 'Son güncelleme / Last updated: ' + fmtTime(new Date());
    }).then(function () { setLoading(false); });
  }
  refresh();
  setInterval(refresh, REFRESH_MS);
})();
