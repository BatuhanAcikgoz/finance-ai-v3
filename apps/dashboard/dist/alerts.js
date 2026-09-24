/* ===========================================================================
 * Alerts inbox page — vanilla JS
 * Reads /api/v1/alerts; falls back to a synthetic list so dev preview never
 * shows an empty page. Row click marks as read locally + expands inline.
 * Filters: severity (all / critical / warn / info) + status (all / unread / read)
 * ========================================================================= */
(function () {
  'use strict';

  var API_BASE = '/api';
  var REFRESH_MS = 30000;

  var SYNTHETIC = [
    {
      id: 'a-001',
      ts: '2026-09-24T08:14:22+03:00',
      severity: 'critical',
      title: 'THYAO weight exceeds drift limit',
      source: 'risk-engine',
      detail: 'THYAO reached 18.4% (target 18.0%); drift limit exceeded by 40 bps. Rebalance recommended within 24h.',
    },
    {
      id: 'a-002',
      ts: '2026-09-24T07:55:01+03:00',
      severity: 'warn',
      title: 'KAP feed backlog rising',
      source: 'kap-collector',
      detail: 'kap-collector queue depth = 4,820 events. Batch processor will drain within ~6 minutes.',
    },
    {
      id: 'a-003',
      ts: '2026-09-24T07:31:45+03:00',
      severity: 'warn',
      title: 'LLM cost nearing daily budget',
      source: 'agent-supervisor',
      detail: '$42.18 / $50.00 daily budget used (84%). Decision generation may throttle if breached.',
    },
    {
      id: 'a-004',
      ts: '2026-09-24T06:12:09+03:00',
      severity: 'info',
      title: 'Daily report delivered',
      source: 'report-generator',
      detail: '2026-09-24.pdf generated and stored; available at /reports/2026-09-24.pdf',
    },
    {
      id: 'a-005',
      ts: '2026-09-24T05:42:31+03:00',
      severity: 'info',
      title: 'Scheduler tick — market open',
      source: 'decision-engine',
      detail: 'BIST opened; first tick received at 09:42 TRT. Now monitoring 48 symbols.',
    },
    {
      id: 'a-006',
      ts: '2026-09-23T22:10:00+03:00',
      severity: 'critical',
      title: 'PostgreSQL replica lag > 30s',
      source: 'postgres-monitor',
      detail: 'replica-2 (analytics) lagged primary by 47s at 22:09:51. Self-resolved at 22:10:14.',
    },
    {
      id: 'a-007',
      ts: '2026-09-23T18:05:14+03:00',
      severity: 'warn',
      title: 'Qdrant collection near capacity',
      source: 'qdrant-monitor',
      detail: 'decisions_v3 collection at 92% (1,840 / 2,000 shards provisioned).',
    },
  ];

  var sevFilter = 'all';
  var statusFilter = 'all';
  var readSet = {};           // local-only: ids of alerts the user clicked
  var localData = null;       // last fetched list

  // ---- DOM refs -------------------------------------------------------------
  var $list         = document.getElementById('alerts-list');
  var $refreshInd   = document.getElementById('refresh-indicator');
  var $refreshText  = document.getElementById('refresh-text');
  var $sevChips     = document.getElementById('sev-chips');
  var $statusChips  = document.getElementById('status-chips');
  var $meta         = document.getElementById('meta');

  // ---- Helpers --------------------------------------------------------------
  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fmtTime(iso) {
    var d = (typeof iso === 'string') ? new Date(iso) : (iso instanceof Date ? iso : null);
    if (!d || isNaN(d.getTime())) return '';
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      + ' ' + d.toLocaleDateString('en-GB');
  }
  function setLoading(b) {
    if (b) { $refreshInd.classList.add('is-loading'); $refreshText.textContent = 'yenileniyor / refreshing…'; }
    else   { $refreshInd.classList.remove('is-loading'); $refreshText.textContent = 'idle'; }
  }

  // Try to read the existing /v1/alerts endpoint via api-gateway.
  function loadAlerts() {
    setLoading(true);
    return fetch(API_BASE + '/v1/alerts', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (body) {
        // The api-gateway responses can be: { alerts: [...] }, { items: [...] }, [...]
        var arr = (body && (body.alerts || body.items || body.results || body.data)) || body;
        if (Array.isArray(arr) && arr.length) return arr;
        return SYNTHETIC;
      })
      .catch(function () { return SYNTHETIC; });
  }

  function normalise(list) {
    return list.map(function (a, i) {
      return {
        id: a.id || ('a-' + i),
        ts: a.ts || a.timestamp || a.created_at || a.time || new Date().toISOString(),
        severity: (a.severity || a.level || 'info').toLowerCase(),
        title: a.title || a.message || a.summary || '—',
        source: a.source || a.agent || a.component || 'system',
        detail: a.detail || a.description || a.body || '',
      };
    });
  }

  function applyFilters(items) {
    return items.filter(function (a) {
      if (sevFilter !== 'all' && a.severity !== sevFilter) return false;
      var isRead = !!readSet[a.id];
      if (statusFilter === 'unread' &&  isRead) return false;
      if (statusFilter === 'read'   && !isRead) return false;
      return true;
    });
  }

  function render() {
    var items = applyFilters(localData || []);
    if (!items.length) {
      $list.innerHTML = '<li class="empty-state">Tüm uyarılar okundu / All caught up.</li>';
      $meta.textContent = (localData ? localData.length : 0) + ' uyarı / alerts' + (Object.keys(readSet).length ? ' — ' + Object.keys(readSet).length + ' okunmuş / read' : '');
      return;
    }
    var html = items.map(function (a) {
      var isRead = !!readSet[a.id];
      var sevKey = ['critical','warn','info'].indexOf(a.severity) >= 0 ? a.severity : 'info';
      return '' +
        '<li class="alert ' + (isRead ? 'is-read' : 'is-unread') + '" data-id="' + escapeHtml(a.id) + '">' +
        '<div class="alert-row">' +
        '<div style="display:flex; align-items:center; gap:8px;">' +
        '<span class="status-dot ' + (isRead ? 'is-read' : '') + '" aria-hidden="true"></span>' +
        '<span class="sev ' + sevKey + '">' + escapeHtml(sevKey === 'warn' ? 'uyarı' : sevKey === 'critical' ? 'kritik' : 'bilgi') + ' / ' + escapeHtml(a.severity) + '</span>' +
        '<span class="alert-title">' + escapeHtml(a.title) + '</span>' +
        '</div>' +
        '<span style="font-size: 11px; color: var(--muted);">' + escapeHtml(fmtTime(a.ts)) + '</span>' +
        '</div>' +
        '<div class="alert-meta">' +
        '<span>Kaynak / source: <strong style="color: var(--foreground);">' + escapeHtml(a.source) + '</strong></span>' +
        '<span>·</span>' +
        '<span>' + (isRead ? 'okundu / read' : 'okunmamış / unread') + '</span>' +
        '</div>' +
        (a.detail ? '<div class="alert-detail">' + escapeHtml(a.detail) + '</div>' : '') +
        '</li>';
    }).join('');
    $list.innerHTML = html;
    var unread = (localData || []).filter(function (a) { return !readSet[a.id]; }).length;
    $meta.textContent = (localData || []).length + ' uyarı / alerts · ' + unread + ' okunmamış / unread';
  }

  // Click handler (event-delegated): expand + mark read.
  $list.addEventListener('click', function (e) {
    var li = e.target.closest('li.alert');
    if (!li) return;
    var id = li.getAttribute('data-id');
    if (!id) return;
    readSet[id] = true;
    li.classList.remove('is-unread');
    li.classList.add('is-read', 'is-expanded');
    var dot = li.querySelector('.status-dot');
    if (dot) dot.classList.add('is-read');
    // Update meta count once.
    var unread = (localData || []).filter(function (a) { return !readSet[a.id]; }).length;
    $meta.textContent = (localData || []).length + ' uyarı / alerts · ' + unread + ' okunmamış / unread';
  });

  // Chip handlers
  $sevChips.addEventListener('click', function (e) {
    var c = e.target.closest('.chip'); if (!c) return;
    $sevChips.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('is-active'); });
    c.classList.add('is-active');
    sevFilter = c.getAttribute('data-sev') || 'all';
    render();
  });
  $statusChips.addEventListener('click', function (e) {
    var c = e.target.closest('.chip'); if (!c) return;
    $statusChips.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('is-active'); });
    c.classList.add('is-active');
    statusFilter = c.getAttribute('data-status') || 'all';
    render();
  });

  // Boot + refresh
  function refresh() {
    loadAlerts().then(function (data) {
      localData = normalise(data);
      render();
    }).then(function () { setLoading(false); });
  }
  refresh();
  setInterval(refresh, REFRESH_MS);
})();
