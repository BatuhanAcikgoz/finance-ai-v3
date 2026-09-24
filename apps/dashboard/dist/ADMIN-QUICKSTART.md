# Admin Panel + MiniMax-M3 — Hızlı Rehber

## 1. Admin paneline girmek

Tarayıcıdan: **http://localhost:8080/admin.html**

- Sayfa açılır, "Admin Token" input'u görürsün
- Token'ı gir (development'da: `dev_admin_token_change_me`)
- "Kaydet / Save" tıkla
- 4 sekme açılır:
  - **LLM Keys** — provider key CRUD + test
  - **Providers** — 6 provider (openai / anthropic / **minimax** / deepseek / ollama / custom)
  - **System** — CPU/mem/disk/uptime + containers
  - **Audit Log** — admin aksiyonları timeline

## 2. MiniMax-M3 key eklemek

**Admin → LLM Keys → "Yeni key / New key"**

Form:
| Alan | Değer |
|---|---|
| Provider | `minimax` |
| Model | `MiniMax-M3` |
| API Key | **gerçek MiniMax-M3 API key'in** (`eyJ...` gibi) |
| Label | `Production MiniMax` |

"Save" tıkla. Sayfa tabloya yeni satır ekler:
```
provider: minimax
model:    MiniMax-M3
masked:   eyJ...XXXX (son 4 char)
status:   active
```

## 3. Key'i test et

Tabloda key'in satırında **"Test"** butonuna tıkla. Sistem:
1. `https://api.MiniMax.chat/v1/models` adresine bearer token ile GET atar
2. latency_ms ölçer
3. Status günceller:
   - `active` → 200 döndüyse
   - `invalid` → 401/403/404 döndüyse
4. last_error alanına hata metnini yazar

Gerçek key ile **status: active**, `latency_ms: 100-500ms` civarı, `model_count: N` (MiniMax-M3 dahil) görmen lazım.

## 4. Light/Dark toggle

Sağ üst köşede **güneş/ay ikonu** pill button:
- Tıkla → tema değişir (light ↔ dark)
- `localStorage['finance-ai.theme']` kaydedilir
- Sayfa yenilense bile aynı tema açılır
- **Settings sayfasında** (Settings → Theme) "System" seçersen OS tercihi takip edilir

## 5. Settings

**http://localhost:8080/settings.html**

- **Theme**: System / Light / Dark kartları (görsel önizlemeli)
- **Server settings**: notify.email/ws/dashboard, sources.bist_rss/tefas/kap/news, risk.max_position_pct, risk.max_sector_pct, llm.provider/model/monthly_budget_usd
- "Kaydet / Save" → `PATCH /api/v1/settings/` → toast "Kaydedildi"

## 6. Worker'lar hâlâ "heartbeat only"

Worker'lar postgres'e bağlanıyor ama gerçek decision/indicator üretmiyor. Bu ayrı GH issue olarak takipte. Şu an dashboard:
- 10 sembol için günlük OHLCV bars
- 1 karar (subagent test seed)
- 8 alert
- 4 worker "up" ama heartbeat modunda

## 7. Troubleshooting

| Sorun | Çözüm |
|---|---|
| Admin paneli 401 dönüyor | Token yanlış. localStorage temizle: `localStorage.removeItem('finance-ai.admin_token')` |
| Tema yanlış açılıyor | `localStorage.removeItem('finance-ai.theme')` veya Settings → System |
| LLM key test 404 | API key sahte/expired. Test sadece gerçek provider'a ping atar |
| MiniMax provider görünmüyor | Sayfa yenile; provider registry hardcoded |
| Workers "unknown" status | api-gateway container'ında docker CLI yok. /v1/agents/ host'taki docker'a ihtiyaç duyar |
