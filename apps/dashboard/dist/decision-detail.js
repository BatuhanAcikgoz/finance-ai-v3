/* ============================================================================
 * Decision detail page.
 *   GET /api/v1/decisions/{id}   — single decision payload
 *   GET /api/v1/decisions/recent?ticker=… — top 5 past decisions for ticker
 * ============================================================================ */
(function () {
  'use strict';

  // --- DOM refs -------------------------------------------------------------
  var $refresh     = document.getElementById('refresh-indicator');
  var $title       = document.getElementById('page-title');
  var $hdrTicker   = document.getElementById('hdr-ticker');
  var $hdrId       = document.getElementById('hdr-id');
  var $hdrEff      = document.getElementById('hdr-effective');
  var $hdrBadges   = document.getElementById('hdr-badges');
  var $hdrConf     = document.getElementById('hdr-confidence');
  var $summaryText = document.getElementById('summary-text');

  var $actionText  = document.getElementById('action-text');
  var $actionSize  = document.getElementById('action-size');

  var $evidence    = document.getElementById('evidence-stack');
  var $portfolio   = document.getElementById('portfolio-context');
  var $compliance  = document.getElementById('compliance-audit');
  var $llm         = document.getElementById('llm-logs');
  var $similar     = document.getElementById('similar-list');
  var $lastUpd     = document.getElementById('last-updated');

  var CURRENT_ID = null;
  var CURRENT_DECISION = null;

  // --- State ----------------------------------------------------------------
  function setLoading(on) {
    if (on) $refresh.classList.add('is-loading');
    else    $refresh.classList.remove('is-loading');
  }

  function el(id) { return document.getElementById(id); }

  // --- Renderers ------------------------------------------------------------
  function renderHeader(d) {
    $title.textContent = 'Karar / ' + (d.ticker || '—');
    $hdrTicker.textContent = d.ticker || '—';
    $hdrId.textContent = d.decision_id || '—';
    var ts = d.effective_at || d.created_at || null;
    $hdrEff.textContent = ts
      ? 'Geçerlilik / Effective: ' + window.FA.renderTRT(ts)
      : 'Geçerlilik / Effective: —';

    var badges = '';
    badges += window.FA.renderActionBadge(d.action) + ' ';
    badges += window.FA.renderComplianceBadge(d.compliance_status);
    $hdrBadges.innerHTML = badges;

    $hdrConf.innerHTML = ''
      + '<div style="display:flex;flex-direction:column;align-items:center;gap:6px;">'
      +   '<span class="subtle">Güven / Confidence</span>'
      +   window.FA.renderConfidenceMeter(d.confidence)
      + '</div>';
  }

  function renderSummary(d) {
    var reason = d.supervisor_reasoning || '';
    var sizePct = d.position_size_pct;
    var sizeTxt = (sizePct !== null && sizePct !== undefined && !isNaN(Number(sizePct)))
      ? 'Önerilen pozisyon büyüklüğü / Suggested size: ' + (Number(sizePct) * 100).toFixed(1) + '%'
      : 'Önerilen pozisyon büyüklüğü / Suggested size: —';

    $summaryText.innerHTML = reason
      ? '<strong>Gerekçe / Reasoning:</strong> ' + window.FA.esc(reason)
      : '<span style="color:var(--muted)">Gerekçe girilmemiş / No reasoning recorded.</span>';

    $actionText.innerHTML  = reason
      ? window.FA.esc(reason)
      : '<span style="color:var(--muted)">Bu karar için aksiyon özeti yok / No action summary recorded.</span>';
    $actionSize.textContent = sizeTxt;
  }

  function renderEvidence(d) {
    // decision.evidence from the api-gateway is a JSON-encoded string.
    var parsed = window.FA.parseJsonb(d.evidence);
    var list = [];
    if (Array.isArray(parsed))          list = parsed;
    else if (parsed && typeof parsed === 'object') {
      // Some backends serialise as {streams: [...]}; fall back to that.
      if (Array.isArray(parsed.streams))         list = parsed.streams;
      else if (Array.isArray(parsed.evidence))  list = parsed.evidence;
    }

    if (!list.length) {
      var emptyMsg = ''
        + '<div class="empty-state">'
        +   'Bu karar için kanıt kaydı henüz oluşturulmadı.<br/>'
        +   '<span class="subtle">No evidence captured for this decision yet '
        +   '(evidence_count = ' + window.FA.esc(d.evidence_count || 0) + ').</span>'
        + '</div>';
      if (d.contradiction_score && Number(d.contradiction_score) > 0) {
        emptyMsg += '<p class="subtle">Çelişki skoru / Contradiction score: '
          + (Number(d.contradiction_score) * 100).toFixed(1) + '%</p>';
      }
      $evidence.innerHTML = emptyMsg;
      return;
    }
    $evidence.innerHTML = list.map(window.FA.renderEvidenceCard.bind(window.FA)).join('');
  }

  function renderPortfolio(d) {
    var ctx = window.FA.parseJsonb(d.portfolio_context);
    if (!ctx || typeof ctx !== 'object') {
      $portfolio.innerHTML = ''
        + '<div class="empty-state">'
        +   'Portföy bağlamı kaydedilmemiş / No portfolio context captured.'
        +   '<br/><span class="subtle">position_size_pct = '
        +   window.FA.esc(d.position_size_pct === null ? '—' : (Number(d.position_size_pct) * 100).toFixed(1) + '%')
        +   '</span>'
        + '</div>';
      return;
    }
    var keys = Object.keys(ctx);
    var rows = keys.map(function (k) {
      var v = ctx[k];
      if (v === null || v === undefined) v = '—';
      else if (typeof v === 'object')    v = JSON.stringify(v);
      return '<tr><td class="subtle">' + window.FA.esc(k) + '</td>'
           +     '<td class="num mono">' + window.FA.esc(String(v)) + '</td></tr>';
    }).join('');
    $portfolio.innerHTML = window.FA.renderTable(
      [{ label: 'Alan / Field' }, { label: 'Değer / Value', cls: 'num' }],
      [rows.split('</tr>').filter(Boolean).map(function (r) {
        // renderTable expects rows as arrays of HTML cells — flatten.
        var m = r.match(/<td class="subtle">([\s\S]*?)<\/td>\s*<td class="num mono">([\s\S]*?)<\/td>/);
        return m ? [m[1], m[2]] : [r];
      })]
    );
  }

  function renderCompliance(d) {
    var status = d.compliance_status || '—';
    var reviewedAt = d.compliance_reason || null;  // API stores "reason" text, not a timestamp.
    var html = ''
      + '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
      +   '<span>Durum / Status:</span>'
      +   window.FA.renderComplianceBadge(status)
      + '</div>'
      + '<p class="subtle" style="margin-top:8px;">';
    if (reviewedAt) {
      html += 'Gerekçe / Reason: ' + window.FA.esc(reviewedAt);
    } else {
      html += 'İnceleme zamanı / Reviewed at: henüz kaydedilmedi / not recorded.';
    }
    html += '</p>';
    $compliance.innerHTML = html;
  }

  function renderLlmLogs(d) {
    // The current schema doesn't expose per-call LLM logs — surface the
    // prompt_versions JSONB so the section never reads "data missing"
    // outright.
    var promptVersions = window.FA.parseJsonb(d.prompt_versions);
    var rows = [];

    if (promptVersions && typeof promptVersions === 'object' && !Array.isArray(promptVersions)) {
      var keys = Object.keys(promptVersions);
      if (keys.length) {
        keys.forEach(function (k) {
          var v = promptVersions[k];
          if (v === null || v === undefined) v = '—';
          if (typeof v === 'object') v = JSON.stringify(v);
          rows.push([
            window.FA.esc(k),
            '<span class="subtle">—</span>',
            '<span class="num subtle">—</span>',
            '<span class="num subtle">—</span>',
            '<span class="num subtle">—</span>',
            '<span class="num subtle">—</span>',
            '<code>' + window.FA.esc(String(v)) + '</code>',
          ]);
        });
      }
    }

    if (!rows.length) {
      $llm.innerHTML = ''
        + '<div class="empty-state">'
        +   'LLM çağrı logları henüz mevcut değil / No per-call LLM logs available yet.'
        +   '<br/><span class="subtle">Bu alan, agent çağrılarına ilişkin token ve maliyet verisi geldikçe dolacak.</span>'
        + '</div>';
      return;
    }
    $llm.innerHTML = window.FA.renderTable([
      { label: 'Sağlayıcı / Provider' },
      { label: 'Model' },
      { label: 'Prompt tok.', cls: 'num' },
      { label: 'Completion tok.', cls: 'num' },
      { label: 'Latency (ms)', cls: 'num' },
      { label: 'Maliyet (USD)', cls: 'num' },
      { label: 'Agent ID / Prompt version' },
    ], rows);
  }

  function renderSimilar(d, list) {
    if (!list || !list.length) {
      $similar.innerHTML = ''
        + '<div class="empty-state">'
        +   'Benzer geçmiş karar yok / No similar past decisions.'
        +   '<br/><span class="subtle">Qdrant semantik araması henüz bağlı değil; '
        +   'aynı sembolün son kararları listeleniyor.</span>'
        + '</div>';
      return;
    }
    var rows = list.slice(0, 5).map(function (other) {
      var outcome = other.outcome || null;
      var hitMiss = outcome === null || outcome === undefined
        ? '<span class="subtle">—</span>'
        : (outcome === 'hit' || outcome === true || outcome === 1
           ? '<span style="color:var(--accent)">● isabet / hit</span>'
           : '<span style="color:var(--danger)">● ıskaladı / miss</span>');
      var eff = other.effective_at || other.created_at || null;
      var href = window.FA.detailUrl(other.decision_id);
      return [
        '<a href="' + window.FA.esc(href) + '">' + window.FA.esc(window.FA.shortId(other.decision_id)) + '</a>',
        window.FA.renderActionBadge(other.action),
        '<span class="num">' + window.FA.esc((Number(other.confidence) * 100).toFixed(0) + '%') + '</span>',
        window.FA.esc(window.FA.renderTRT(eff)),
        hitMiss,
      ];
    });
    $similar.innerHTML = ''
      + '<p class="subtle" style="margin:0 0 10px">'
      +   'Aynı sembolün son kararları — Qdrant benzerlik skoru henüz mevcut değil.'
      + '</p>'
      + window.FA.renderTable([
        { label: 'ID' },
        { label: 'Aksiyon / Action' },
        { label: 'Güven / Confidence', cls: 'num' },
        { label: 'Geçerlilik / Effective' },
        { label: 'Sonuç / Outcome' },
      ], rows);
  }

  // --- Data load ------------------------------------------------------------
  function fetchDecision(id) {
    return window.FA.fetchJson(window.FA.API_BASE + '/v1/decisions/' + encodeURIComponent(id));
  }

  function fetchSimilar(ticker, excludeId) {
    if (!ticker) return Promise.resolve([]);
    return window.FA.fetchJson(window.FA.API_BASE + '/v1/decisions/recent', {
      params: { ticker: ticker, limit: 20 }
    })
    .then(function (data) {
      var list = window.FA.normalizeList(data);
      return list.filter(function (d) { return d.decision_id !== excludeId; });
    })
    .catch(function () { return []; });
  }

  function render404() {
    $title.textContent = 'Karar bulunamadı / Decision not found';
    $hdrTicker.textContent = '—';
    $hdrId.textContent = CURRENT_ID || '—';
    $hdrEff.textContent = '';
    $hdrBadges.innerHTML = '';
    $hdrConf.innerHTML = '';
    $summaryText.innerHTML = '';
    $actionText.innerHTML = '';
    $actionSize.textContent = '';
    $evidence.innerHTML = ''
      + '<div class="error-state">'
      +   '<p><strong>Karar bulunamadı / Decision not found.</strong></p>'
      +   '<p class="subtle">Aradığınız karar silinmiş veya hiç var olmamış olabilir.</p>'
      +   '<p style="margin-top:10px;"><a href="decisions.html">← Tüm kararlar / All decisions</a></p>'
      + '</div>';
    $portfolio.innerHTML = '';
    $compliance.innerHTML = '';
    $llm.innerHTML = '';
    $similar.innerHTML = '';
  }

  function loadAndRender() {
    var id = CURRENT_ID;
    if (!id) return;
    setLoading(true);

    fetchDecision(id)
      .then(function (d) {
        CURRENT_DECISION = d;
        renderHeader(d);
        renderSummary(d);
        renderEvidence(d);
        renderPortfolio(d);
        renderCompliance(d);
        renderLlmLogs(d);
        $lastUpd.textContent = 'son güncelleme ' + window.FA.fmtTime(new Date());
        // Similar is best-effort; don't block the main render.
        return fetchSimilar(d.ticker, id).then(function (sim) {
          renderSimilar(d, sim);
        });
      })
      .catch(function (err) {
        if (err && err.status === 404) {
          render404();
        } else {
          $evidence.innerHTML = ''
            + '<div class="error-state">'
            +   'Karar yüklenemedi / Failed to load decision: '
            +   window.FA.esc(err && err.message ? err.message : 'bilinmeyen hata')
            + '</div>';
        }
      })
      .then(function () { setLoading(false); });
  }

  // --- Bootstrap ------------------------------------------------------------
  function boot() {
    CURRENT_ID = window.FA.getQueryParam('id');
    if (!CURRENT_ID) {
      $evidence.innerHTML = ''
        + '<div class="error-state">'
        +   'Karar ID belirtilmedi / No decision id supplied.'
        +   '<br/><a href="decisions.html">← Tüm kararlar / All decisions</a>'
        + '</div>';
      return;
    }
    loadAndRender();
    window.FA.attachRefreshLoop(loadAndRender, 60000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();