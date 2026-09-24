# Portföy Yönetimi

Bu dokümantasyon, Finance AI V3 sisteminde portföy yönetiminin nasıl yapıldığını açıklar.

## 📋 İçindekiler

1. [Portföy Oluşturma](#portföy-oluşturma)
2. [Portföy Detaylarını Görme](#portföy-detaylarını-görme)
3. [Pozisyon Ekleme](#pozisyon-ekleme)
4. [Pozisyon Güncelleme](#pozisyon-güncelleme)
5. [Pozisyon Kaldırma](#pozisyon-kaldırma)
6. [Rebalancing](#rebalancing)
7. [Portföy Performansı](#portföy-performansı)

---

## Portföy Oluşturma

### API İsteği

```bash
POST /api/v1/portfolios
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Yeni Portföy",
  "base_currency": "TRY",
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25,
  "max_sector_pct": 0.40
}
```

### Yanıt

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Yeni Portföy",
  "base_currency": "TRY",
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25,
  "max_sector_pct": 0.40,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Parametreler

| Parametre | Tip | Açıklama | Zorunlu | Varsayılan |
|-----------|-----|----------|---------|------------|
| `name` | string | Portföy adı | Evet | - |
| `base_currency` | string | Para birimi (TRY, USD, EUR) | Hayır | TRY |
| `risk_budget_pct` | float | Yıllık risk bütçesi (%) | Hayır | 0.03 |
| `max_position_pct` | float | Maksimum tek pozisyon (%) | Hayır | 0.25 |
| `max_sector_pct` | float | Maksimum sektör ağırlığı (%) | Hayır | 0.40 |

---

## Portföy Detaylarını Görme

### Tüm Portföyleri Listeleme

```bash
GET /api/v1/portfolios
Authorization: Bearer <token>
```

### Tek Portföy Detayı

```bash
GET /api/v1/portfolios/{portfolio_id}
Authorization: Bearer <token>
```

### Örnek Yanıt

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "user-uuid",
  "name": "Ana Portföy",
  "base_currency": "TRY",
  "total_value_try": 1000000.00,
  "cash_try": 150000.00,
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25,
  "max_sector_pct": 0.40,
  "holdings": [
    {
      "ticker": "THYAO",
      "shares": 1000,
      "current_price": 180.50,
      "current_value_try": 180500.00,
      "current_weight": 0.1805,
      "target_weight": 0.15,
      "cost_basis_try": 150000.00,
      "unrealized_pnl_try": 30500.00,
      "unrealized_pnl_pct": 0.203
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

## Pozisyon Ekleme

### Mevcut Pozisyon Ekleme

Elimizdeki hisseleri portföye ekler:

```bash
POST /api/v1/portfolios/{portfolio_id}/positions
Authorization: Bearer <token>
Content-Type: application/json

{
  "ticker": "GARAN",
  "shares": 5000,
  "cost_basis_try": 375000.00,
  "acquisition_date": "2024-01-10"
}
```

### Takip Listesine Ekleme

Sadece takip etmek için (pozisyon yok):

```bash
POST /api/v1/portfolios/{portfolio_id}/holdings
Authorization: Bearer <token>
Content-Type: application/json

{
  "ticker": "ASELS",
  "target_weight": 0.10
}
```

---

## Pozisyon Güncelleme

### Hedef Ağırlık Güncelleme

```bash
PATCH /api/v1/portfolios/{portfolio_id}/holdings/{ticker}
Authorization: Bearer <token>
Content-Type: application/json

{
  "target_weight": 0.12
}
```

### Maliyet Güncelleme

```bash
PATCH /api/v1/portfolios/{portfolio_id}/positions/{ticker}
Authorization: Bearer <token>
Content-Type: application/json

{
  "cost_basis_try": 400000.00
}
```

---

## Pozisyon Kaldırma

### Takip listesinden kaldırma:

```bash
DELETE /api/v1/portfolios/{portfolio_id}/holdings/{ticker}
Authorization: Bearer <token>
```

### Tüm pozisyonu satma:

```bash
POST /api/v1/portfolios/{portfolio_id}/sell-all/{ticker}
Authorization: Bearer <token>
```

---

## Rebalancing

### Rebalancing Nedir?

Portföydeki mevcut ağırlıklar, hedef ağırlıklardan saptığında sistem otomatik olarak rebalancing önerileri üretir.

### Rebalancing Önerilerini Görme

```bash
GET /api/v1/portfolios/{portfolio_id}/rebalance
Authorization: Bearer <token>
```

### Örnek Yanıt

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "recommendations": [
    {
      "ticker": "THYAO",
      "current_weight": 0.22,
      "target_weight": 0.15,
      "drift_pct": 0.07,
      "action": "SELL",
      "estimated_shares": 350,
      "estimated_value_try": 63175.00,
      "priority": 7
    },
    {
      "ticker": "GARAN",
      "current_weight": 0.08,
      "target_weight": 0.12,
      "drift_pct": 0.04,
      "action": "BUY",
      "estimated_shares": 400,
      "estimated_value_try": 30000.00,
      "priority": 4
    }
  ]
}
```

### Drift Eşik Değerleri

| Drift (%) | Aksiyon |
|-----------|---------|
| < 2% | İşlem yapma |
| 2-5% | Hafif uyarı |
| 5-10% | Rebalance öner |
| > 10% | Acil rebalance |

---

## Portföy Performansı

### Performans Özeti

```bash
GET /api/v1/portfolios/{portfolio_id}/performance
Authorization: Bearer <token>
```

### Örnek Yanıt

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "period": {
    "start": "2024-01-01",
    "end": "2024-01-15"
  },
  "total_value_try": 1050000.00,
  "total_return_pct": 5.0,
  "holdings": [
    {
      "ticker": "THYAO",
      "return_pct": 20.3,
      "contribution_pct": 3.5
    }
  ],
  "benchmark": {
    "name": "BIST 100",
    "return_pct": 3.2,
    "alpha": 1.8
  }
}
```

### Risk Metrikleri

```bash
GET /api/v1/portfolios/{portfolio_id}/risk
Authorization: Bearer <token>
```

```json
{
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "var_95_1d": 15000.00,
  "cvar_95_1d": 22500.00,
  "portfolio_beta": 1.15,
  "portfolio_volatility": 0.18,
  "concentration_hhi": 0.12,
  "assessed_at": "2024-01-15T10:30:00Z"
}
```

| Metrik | Açıklama |
|--------|----------|
| VaR 95% 1D | %95 güvenle 1 günde kaybedilebilecek maksimum |
| CVaR 95% 1D | Ortalama kayıp (VaR aşıldığında) |
| Beta | Piyasa duyarlılığı |
| Volatility | Standart sapma (yıllıklaştırılmış) |
| HHI | Konsantrasyon endeksi (0=çeşitli, 1=tek hisse) |

---

## ⚠️ Önemli Notlar

1. **Maliyet Bazı**: Pozisyon eklerken doğru maliyet bazı girin. Bu, kar/zarar hesaplamasını etkiler.

2. **Risk Limitleri**: Sistem, belirlediğiniz risk limitlerini aşmanıza izin vermez.

3. **Döviz**: Farklı para birimlerindeki varlıklar, portföy toplamına eklenirken dönüştürülür.

4. **Piyasa Saatleri**: İşlemler yalnızca BIST açıkken gerçekleştirilir (09:30-18:00 TRT).

---

## Sonraki Adımlar

- [Karar Sistemi](decision-system.md) - Trading kararlarını anlama
- [Risk Yönetimi](risk-management.md) - Risk metriklerini anlama
