# 15/01 — Email Templates

## Morning Briefing Template

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Finance AI V3 — Sabah Bülteni</title>
</head>
<body style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">

  <!-- Header -->
  <div style="background: #2563EB; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
    <h1 style="margin: 0;">Finance AI V3</h1>
    <p style="margin: 5px 0 0;">Sabah Bülteni — {{ date_tr }}</p>
  </div>

  <!-- Disclaimer (top) -->
  <div style="background: #FEF3C7; padding: 10px; font-size: 11px; color: #92400E;">
    Bu rapor yatırım tavsiyesi değildir. Yatırım kararlarınızı kendi araştırmanızla destekleyiniz.
  </div>

  <!-- Executive Summary -->
  <h2>Özet</h2>
  <p>{{ executive_summary_tr }}</p>

  <!-- Today's Decisions -->
  <h2>Bugünün Kararları ({{ decisions_count }})</h2>
  {% for group in decision_groups %}
  <div style="border: 1px solid #E5E7EB; padding: 15px; margin: 10px 0; border-radius: 6px;">
    <h3 style="color: {{ '#16A34A' if group.action == 'BUY' else '#DC2626' if group.action in ['SELL','REDUCE'] else '#6B7280' }};">
      {{ group.ticker }} — {{ group.action }}
    </h3>
    <p>{{ group.narrative_tr }}</p>
    <p style="font-size: 12px; color: #6B7280;">
      Güven: {{ "%.0f" | format(group.confidence * 100) }}% · 
      Pozisyon: {{ "%.1f" | format(group.position_size_pct * 100) }}% · 
      Karar ID: {{ group.decision_ids[0][:8] }}
    </p>
  </div>
  {% endfor %}

  <!-- Action Items -->
  <h2>Önerilen Aksiyonlar</h2>
  <ol>
    {% for item in action_items_tr %}
    <li>{{ item }}</li>
    {% endfor %}
  </ol>

  <!-- Risk Snapshot -->
  <h2>Risk Özeti</h2>
  <table style="width: 100%; border-collapse: collapse;">
    <tr><td>1-gün 95% VaR</td><td>{{ "%.2f" | format(risk.var_1d_95 * 100) }}%</td></tr>
    <tr><td>Beta (BIST-100)</td><td>{{ "%.2f" | format(risk.beta_to_bist100) }}</td></tr>
    <tr><td>Konsantrasyon (HHI)</td><td>{{ "%.3f" | format(risk.hhi_concentration) }}</td></tr>
  </table>

  <!-- Disclaimer (bottom) -->
  <div style="background: #FEF3C7; padding: 10px; font-size: 11px; color: #92400E; margin-top: 20px;">
    Bu rapor yatırım tavsiyesi değildir. Yatırım kararlarınızı kendi araştırmanızla destekleyiniz.
    Geçmiş performans gelecek getirinin garantisi değildir.
  </div>

  <!-- Footer -->
  <div style="text-align: center; font-size: 11px; color: #9CA3AF; margin-top: 20px;">
    <p>Finance AI V3 · <a href="{{ dashboard_url }}">Dashboard'a git</a></p>
    <p><a href="{{ unsubscribe_url }}">Abonelikten çık</a></p>
  </div>

</body>
</html>
```

## Critical Alert Template (much shorter)

```html
<body style="font-family: Inter, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
  <div style="background: #DC2626; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
    <h2>⚠️ {{ severity }}: {{ title_tr }}</h2>
  </div>
  <div style="border: 1px solid #E5E7EB; padding: 15px;">
    <p>{{ body_tr }}</p>
    <p><strong>Önerilen aksiyon:</strong> {{ action_suggested }}</p>
    <p style="font-size: 12px; color: #6B7280;">
      Ticker: {{ ticker }} · Karar ID: {{ decision_id }} · {{ sent_at_tr }}
    </p>
    <a href="{{ dashboard_url }}/decisions/{{ decision_id }}" 
       style="display: inline-block; background: #2563EB; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
      Karar detayını gör
    </a>
  </div>
  <div style="font-size: 11px; color: #92400E; margin-top: 10px;">
    Bu bildirim yatırım tavsiyesi değildir.
  </div>
</body>
```
