# API Referansı

Finance AI V3 REST API tam dokümantasyonu.

## 📋 İçindekiler

1. [Genel Bilgiler](#genel-bilgiler)
2. [Kimlik Doğrulama](#kimlik-doğrulama)
3. [Portföy API](#portföy-api)
4. [Kararlar API](#kararlar-api)
5. [Piyasa Verisi API](#piyasa-verisi-api)
6. [Bildirimler API](#bildirimler-api)
7. [Şemalar](#şemalar)

---

## Genel Bilgiler

### Base URL

```
Development: http://localhost:8000/api/v1
Staging: https://staging.finance-ai-v3.com/api/v1
Production: https://api.finance-ai-v3.com/api/v1
```

### İstek Formatı

```http
Content-Type: application/json
Authorization: Bearer <token>
```

### Yanıt Formatı

```json
{
  "data": { },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}
```

### Hata Formatı

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Geçersiz istek parametreleri",
    "details": [
      {
        "field": "ticker",
        "message": "Ticker sembolü zorunludur"
      }
    ]
  }
}
```

---

## Kimlik Doğrulama

### Token Alma

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "username": "kullanici",
  "password": "sifre"
}
```

**Yanıt (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Token Yenileme

```http
POST /api/v1/auth/refresh
Authorization: Bearer <token>
```

---

## Portföy API

### Portföy Oluştur

```http
POST /api/v1/portfolios
Authorization: Bearer <token>
```

**İstek:**

```json
{
  "name": "Ana Portföy",
  "base_currency": "TRY",
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25,
  "max_sector_pct": 0.40
}
```

**Yanıt (201):**

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "user-uuid",
  "name": "Ana Portföy",
  "base_currency": "TRY",
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25,
  "max_sector_pct": 0.40,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Portföy Listele

```http
GET /api/v1/portfolios
Authorization: Bearer <token>
```

**Query Parameters:**

| Parametre | Tip | Açıklama |
|-----------|-----|----------|
| page | int | Sayfa numarası (varsayılan: 1) |
| per_page | int | Sayfa başı kayıt (varsayılan: 20) |

### Portföy Detayı

```http
GET /api/v1/portfolios/{portfolio_id}
Authorization: Bearer <token>
```

### Portföy Güncelle

```http
PATCH /api/v1/portfolios/{portfolio_id}
Authorization: Bearer <token>
```

**İstek:**

```json
{
  "name": "Yeni İsim",
  "risk_budget_pct": 0.05
}
```

### Portföy Sil

```http
DELETE /api/v1/portfolios/{portfolio_id}
Authorization: Bearer <token>
```

---

## Kararlar API

### Karar Listele

```http
GET /api/v1/portfolios/{portfolio_id}/decisions
Authorization: Bearer <token>
```

**Query Parameters:**

| Parametre | Tip | Açıklama |
|-----------|-----|----------|
| ticker | string | Hisse senedi filtresi |
| action | string | Aksiyon filtresi (BUY, SELL, HOLD) |
| start_date | date | Başlangıç tarihi |
| end_date | date | Bitiş tarihi |
| min_confidence | float | Minimum güven |
| page | int | Sayfa numarası |
| per_page | int | Sayfa başı kayıt |

### Karar Detayı

```http
GET /api/v1/portfolios/{portfolio_id}/decisions/{decision_id}
Authorization: Bearer <token>
```

### Karar Oluştur (Manual)

```http
POST /api/v1/portfolios/{portfolio_id}/decisions
Authorization: Bearer <token>
```

**İstek:**

```json
{
  "ticker": "THYAO"
}
```

---

## Piyasa Verisi API

### Hisse Senedi Fiyatı

```http
GET /api/v1/market/quote/{ticker}
Authorization: Bearer <token>
```

**Yanıt:**

```json
{
  "ticker": "THYAO",
  "name": "Türk Hava Yolları",
  "price": 180.50,
  "change_pct": 2.35,
  "volume": 1500000,
  "bid": 180.25,
  "ask": 180.75,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Çoklu Fiyat

```http
POST /api/v1/market/quotes
Authorization: Bearer <token>
```

**İstek:**

```json
{
  "tickers": ["THYAO", "GARAN", "ASELS"]
}
```

### Endeks Değerleri

```http
GET /api/v1/market/indices
Authorization: Bearer <token>
```

**Yanıt:**

```json
{
  "indices": [
    {
      "code": "XU100",
      "name": "BIST 100",
      "value": 8000.25,
      "change_pct": 1.5
    },
    {
      "code": "XU030",
      "name": "BIST 30",
      "value": 8500.50,
      "change_pct": 1.8
    }
  ]
}
```

### Tarihsel Veri

```http
GET /api/v1/market/bars/{ticker}
Authorization: Bearer <token>
```

**Query Parameters:**

| Parametre | Tip | Açıklama | Varsayılan |
|-----------|-----|----------|------------|
| timeframe | string | Zaman dilimi (1m, 5m, 15m, 60m, 1d) | 1d |
| start_date | date | Başlangıç | 30 gün önce |
| end_date | date | Bitiş | bugün |
| limit | int | Max kayıt | 100 |

---

## Bildirimler API

### Bildirim Ayarları

```http
GET /api/v1/notifications/settings
Authorization: Bearer <token>
```

### Bildirim Ayarlarını Güncelle

```http
PUT /api/v1/notifications/settings
Authorization: Bearer <token>
```

**İstek:**

```json
{
  "email_enabled": true,
  "push_enabled": false,
  "min_grade": "WARN",
  "tickers": ["THYAO", "GARAN"],
  "notification_types": ["DECISION_NEW", "REBALANCE_NEEDED"]
}
```

### Bildirimleri Listele

```http
GET /api/v1/notifications
Authorization: Bearer <token>
```

### Bildirimi Okundu İşaretle

```http
PATCH /api/v1/notifications/{notification_id}
Authorization: Bearer <token>
```

**İstek:**

```json
{
  "is_read": true
}
```

---

## Şemalar

### Portfolio

```json
{
  "portfolio_id": "uuid",
  "user_id": "uuid",
  "name": "string",
  "base_currency": "TRY | USD | EUR",
  "risk_budget_pct": "float (0-1)",
  "max_position_pct": "float (0-1)",
  "max_sector_pct": "float (0-1)",
  "total_value_try": "float",
  "cash_try": "float",
  "holdings": "[Holding]",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Holding

```json
{
  "ticker": "string",
  "shares": "float",
  "current_price": "float",
  "current_value_try": "float",
  "current_weight": "float",
  "target_weight": "float",
  "cost_basis_try": "float",
  "unrealized_pnl_try": "float",
  "unrealized_pnl_pct": "float"
}
```

### Decision

```json
{
  "decision_id": "uuid",
  "portfolio_id": "uuid",
  "ticker": "string",
  "action": "BUY | SELL | HOLD | REDUCE | INSUFFICIENT_EVIDENCE",
  "confidence": "float (0-1)",
  "position_size_pct": "float",
  "evidence": "[Evidence]",
  "evidence_count": "int",
  "contradiction_score": "float",
  "supervisor_reasoning": "string",
  "effective_at": "datetime",
  "compliance_status": "PENDING | APPROVED | BLOCKED",
  "data_completeness": "complete | partial | missing"
}
```

### Evidence

```json
{
  "stream": "technical | fundamental | sentiment | sector | macro",
  "signal": "BULLISH | NEUTRAL | BEARISH",
  "strength": "float (0-1)",
  "confidence": "float (0-1)",
  "source_id": "string"
}
```
