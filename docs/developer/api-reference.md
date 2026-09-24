# API Referansı

Finance AI V3 REST API endpoint'leri.

## 📋 İçindekiler

1. [Genel Bilgiler](#genel-bilgiler)
2. [Kimlik Doğrulama](#kimlik-doğrulama)
3. [Portföy API](#portföy-api)
4. [Kararlar API](#kararlar-api)
5. [Piyasa Verisi API](#piyasa-verisi-api)
6. [Bildirimler API](#bildirimler-api)
7. [Hata Kodları](#hata-kodları)

---

## Genel Bilgiler

### Base URL

```
Development: http://localhost:8000/api/v1
Production:  https://api.finance-ai-v3.com/api/v1
```

### Content Type

Tüm istekler ve yanıtlar JSON formatındadır:

```
Content-Type: application/json
```

### Rate Limiting

| Endpoint Grubu | Limit |
|---------------|-------|
| Genel API | 100 istek/dakika |
| Auth endpoints | 10 istek/dakika |
| Yazma işlemleri | 50 istek/dakika |

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

### Yanıt

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Token Kullanımı

```http
GET /api/v1/portfolios
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## Portföy API

### Portföy Oluşturma

```http
POST /api/v1/portfolios
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Ana Portföy",
  "base_currency": "TRY",
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25,
  "max_sector_pct": 0.40
}
```

**Yanıt (201 Created):**

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Ana Portföy",
  "base_currency": "TRY",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Portföy Listeleme

```http
GET /api/v1/portfolios
Authorization: Bearer <token>
```

### Portföy Detayı

```http
GET /api/v1/portfolios/{portfolio_id}
Authorization: Bearer <token>
```

### Portföy Silme

```http
DELETE /api/v1/portfolios/{portfolio_id}
Authorization: Bearer <token>
```

### Pozisyon Ekleme

```http
POST /api/v1/portfolios/{portfolio_id}/positions
Authorization: Bearer <token>
Content-Type: application/json

{
  "ticker": "THYAO",
  "shares": 1000,
  "cost_basis_try": 150000.00
}
```

### Pozisyon Güncelleme

```http
PATCH /api/v1/portfolios/{portfolio_id}/positions/{ticker}
Authorization: Bearer <token>
Content-Type: application/json

{
  "shares": 1500,
  "cost_basis_try": 200000.00
}
```

### Rebalancing Önerileri

```http
GET /api/v1/portfolios/{portfolio_id}/rebalance
Authorization: Bearer <token>
```

---

## Kararlar API

### Karar Listeleme

```http
GET /api/v1/portfolios/{portfolio_id}/decisions
Authorization: Bearer <token>
```

### Karar Detayı

```http
GET /api/v1/portfolios/{portfolio_id}/decisions/{decision_id}
Authorization: Bearer <token>
```

### Karar Oluşturma (Manual)

```http
POST /api/v1/portfolios/{portfolio_id}/decisions
Authorization: Bearer <token>
Content-Type: application/json

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
  "price": 180.50,
  "change_pct": 2.35,
  "volume": 1500000,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Çoklu Fiyat

```http
POST /api/v1/market/quotes
Authorization: Bearer <token>
Content-Type: application/json

{
  "tickers": ["THYAO", "GARAN", "ASELS"]
}
```

### Endeks Değerleri

```http
GET /api/v1/market/indices
Authorization: Bearer <token>
```

### Tarihsel Veri

```http
GET /api/v1/market/bars/{ticker}
Authorization: Bearer <token>

Query Parameters:
- timeframe: 1m, 5m, 15m, 60m, 1d (varsayılan: 1d)
- start_date: ISO 8601 tarih
- end_date: ISO 8601 tarih
- limit: max kayıt sayısı (varsayılan: 100)
```

---

## Bildirimler API

### Bildirim Ayarları

```http
GET /api/v1/notifications/settings
Authorization: Bearer <token>
```

```http
PUT /api/v1/notifications/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "email_enabled": true,
  "min_grade": "WARN",
  "tickers": ["THYAO", "GARAN"]
}
```

### Bildirim Listeleme

```http
GET /api/v1/notifications
Authorization: Bearer <token>

Query Parameters:
- is_read: true/false
- grade: INFO, WARN, CRITICAL, EMERGENCY
- portfolio_id: UUID
```

### Bildirimi Okundu İşaretle

```http
PATCH /api/v1/notifications/{notification_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "is_read": true
}
```

---

## Hata Kodları

### HTTP Durum Kodları

| Kod | Açıklama |
|-----|----------|
| 200 | Başarılı |
| 201 | Oluşturuldu |
| 400 | Geçersiz istek |
| 401 | Kimlik doğrulama hatası |
| 403 | Yetki hatası |
| 404 | Bulunamadı |
| 409 | Çakışma |
| 422 | Doğrulama hatası |
| 429 | Rate limit aşıldı |
| 500 | Sunucu hatası |

### Hata Yanıt Formatı

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

### Hata Kodları

| Kod | Açıklama |
|-----|----------|
| `AUTHENTICATION_ERROR` | Geçersiz kimlik bilgileri |
| `TOKEN_EXPIRED` | Token süresi dolmuş |
| `PERMISSION_DENIED` | Yetki yok |
| `VALIDATION_ERROR` | Geçersiz veri |
| `NOT_FOUND` | Kaynak bulunamadı |
| `RATE_LIMIT_EXCEEDED` | Rate limit aşıldı |
| `INTERNAL_ERROR` | Sunucu hatası |

---

## SDK Kullanımı

### Python

```python
import requests

class FinanceAIClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def get_portfolios(self):
        response = requests.get(
            f"{self.base_url}/portfolios",
            headers=self.headers
        )
        return response.json()
    
    def create_portfolio(self, data: dict):
        response = requests.post(
            f"{self.base_url}/portfolios",
            json=data,
            headers=self.headers
        )
        return response.json()

# Kullanım
client = FinanceAIClient("http://localhost:8000/api/v1", "token...")
portfolios = client.get_portfolios()
```

---

## Postman Koleksiyonu

Postman ile test etmek için:

1. Environment değişkenlerini ayarlayın:
   - `base_url`: http://localhost:8000/api/v1
   - `token`: Aldığınız JWT token

2. Collection'ı import edin ve çalıştırın.
