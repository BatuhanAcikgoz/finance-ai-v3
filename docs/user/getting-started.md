# Başlangıç Rehberi

Bu rehber, Finance AI V3 sistemini kullanmaya başlamanız için gereken tüm adımları içerir.

## 📋 İçindekiler

1. [Sisteme Erişim](#sisteme-erişim)
2. [İlk Portföyünüzü Oluşturma](#ilk-portföyünüzü-oluşturma)
3. [Hisse Senedi Ekleme](#hisse-senedi-ekleme)
4. [Kararları İzleme](#kararları-izleme)
5. [Bildirimleri Ayarlama](#bildirimleri-ayarlama)

---

## Sisteme Erişim

### 1. Giriş Yapın

Sisteme giriş için API Gateway üzerinden token almanız gerekir:

```bash
# Token alma
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "kullanici", "password": "sifre"}'
```

Başarılı girişte şu formatta yanıt alırsınız:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 2. Token Kullanımı

Aldığınız token'ı tüm isteklerde `Authorization` header'ında kullanın:

```bash
curl -X GET http://localhost:8000/api/v1/portfolios \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## İlk Portföyünüzü Oluşturma

### Portföy Nedir?

**Portföy**, hisse senedi yatırımlarınızın tamamını temsil eden bir koleksiyondur. Her portföyün:
- Benzersiz bir ID'si vardır
- Belirli bir para birimi cinsindendir (TRY, USD, EUR)
- Risk bütçesi tanımlanabilir
- Pozisyon limitleri belirlenebilir

### Portföy Oluşturma

```bash
curl -X POST http://localhost:8000/api/v1/portfolios \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "İlk Portföyüm",
    "base_currency": "TRY",
    "risk_budget_pct": 0.03,
    "max_position_pct": 0.25,
    "max_sector_pct": 0.40
  }'
```

### Parametre Açıklamaları

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `name` | Portföy adı | Zorunlu |
| `base_currency` | Para birimi | TRY |
| `risk_budget_pct` | Risk bütçesi (%) | 0.03 (3%) |
| `max_position_pct` | Maks. tek pozisyon (%) | 0.25 (25%) |
| `max_sector_pct` | Maks. sektör ağırlığı (%) | 0.40 (40%) |

### Portföy Listeleme

```bash
curl -X GET http://localhost:8000/api/v1/portfolios \
  -H "Authorization: Bearer <token>"
```

---

## Hisse Senedi Ekleme

### Takip Edilecek Hisseleri Belirleme

Sistemin analiz yapabilmesi için portföyünüze hisse senedi eklemeniz gerekir:

```bash
curl -X POST http://localhost:8000/api/v1/portfolios/{portfolio_id}/holdings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "THYAO",
    "target_weight": 0.10
  }'
```

### Desteklenen Hisseler

Sistem, BIST'te işlem gören tüm hisseleri destekler. Yaygın semboller:
- **Bankalar**: GARAN, ISCTR, AKBNK, YKBNK
- **Havacılık**: THYAO, Pegasus (PGSUS)
- **Otomotiv**: ASELS, TOASO, Ford Otosan (FROTO)
- **Perakende**: MIGROS, BIMAS, CarrefourSA (CRFSA)

### Mevcut Pozisyon Ekleme

Zaten sahip olduğunuz bir pozisyonu eklemek için:

```bash
curl -X POST http://localhost:8000/api/v1/portfolios/{portfolio_id}/positions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "THYAO",
    "shares": 1000,
    "cost_basis_try": 150000.00
  }'
```

---

## Kararları İzleme

### Karar Nedir?

Sistem, her hisse senedi için aşağıdaki kararları üretebilir:

| Karar | Açıklama |
|-------|----------|
| **BUY** | Alım önerisi |
| **SELL** | Satım önerisi |
| **HOLD** | Bekle ve tut |
| **REDUCE** | Pozisyonu azalt |
| **INSUFFICIENT_EVIDENCE** | Yetersiz veri |

### Karar Detaylarını Görme

```bash
curl -X GET http://localhost:8000/api/v1/portfolios/{portfolio_id}/decisions \
  -H "Authorization: Bearer <token>"
```

### Örnek Karar Yanıtı

```json
{
  "decision_id": "550e8400-e29b-41d4-a716-446655440000",
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "ticker": "THYAO",
  "action": "BUY",
  "confidence": 0.75,
  "position_size_pct": 0.15,
  "evidence_count": 4,
  "contradiction_score": 0.15,
  "supervisor_reasoning": "THYAO için GÜÇLÜ ALIM önerisi. Sinyal gücü: POZITIF. Güven: %75, Kanıt sayısı: 4.",
  "effective_at": "2024-01-15T10:30:00Z",
  "compliance_status": "APPROVED"
}
```

### Karar Güveni

`confidence` değeri 0-1 arasındadır:

| Değer | Anlamı |
|-------|--------|
| 0.0 - 0.3 | Düşük güven |
| 0.3 - 0.6 | Orta güven |
| 0.6 - 0.8 | Yüksek güven |
| 0.8 - 1.0 | Çok yüksek güven |

---

## Bildirimleri Ayarlama

### Alert Türleri

Sistem farklı önem seviyelerinde bildirimler üretir:

| Seviye | Açıklama |
|--------|----------|
| **INFO** | Bilgilendirme |
| **WARN** | Uyarı |
| **CRITICAL** | Kritik |
| **EMERGENCY** | Acil müdahale gerekli |

### Bildirim Ayarları

```bash
curl -X POST http://localhost:8000/api/v1/notifications/settings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email_enabled": true,
    "min_grade": "WARN",
    "tickers": ["THYAO", "GARAN"]
  }'
```

---

## Sonraki Adımlar

Artık sistemin temel kullanımını biliyorsunuz. Daha fazla bilgi için:

- [Portföy Yönetimi](portfolio-management.md) - Detaylı portföy işlemleri
- [Karar Sistemi](decision-system.md) - Kararların nasıl alındığını anlama
- [SSS](faq.md) - Sıkça sorulan sorular

## ⚠️ Unutmayın

> Finance AI V3 bir **karar destek sistemidir**, **yatırım danışmanı değildir**.
> 
> Tüm yatırım kararlarınızı kendi araştırmanızla destekleyiniz.
