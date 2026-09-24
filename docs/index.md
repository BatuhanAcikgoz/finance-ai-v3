# Finance AI V3 - Başlangıç Rehberi

Hoş geldiniz! Bu rehber, Finance AI V3 sistemini hızlıca tanımanıza ve kullanmaya başlamanıza yardımcı olacaktır.

## 🎯 Bu Sistem Ne Yapar?

Finance AI V3, Türk sermaye piyasalarında (BIST) yatırım kararlarını desteklemek için tasarlanmış bir **Otonom Finansal Araştırma Analisti**dir.

### Ana Yetenekler

| Yetenek | Açıklama |
|---------|----------|
| **Veri Toplama** | BIST hisse senetleri, KAP açıklamaları, haberler, makro veriler |
| **Teknik Analiz** | 20+ teknik gösterge ile otomatik sinyal üretimi |
| **Temel Analiz** | Mali rapor ve açıklamalardan oran çıkarımı |
| **Karar Mekanizması** | Çoklu kanıt birleştirme ile trading kararları |
| **Portföy Yönetimi** | Otomatik rebalancing ve pozisyon takibi |
| **Risk Yönetimi** | VaR, CVaR, konsantrasyon analizi |
| **Uyumluluk Kontrolü** | Yasal uyumluluk ve yatırım kısıtlamaları |

## 🏗️ Sistem Mimarisi

Finance AI V3, **mikroservis mimarisi** kullanır. Her servis belirli bir işlevi yerine getirir:

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway                              │
│                  (Tüm istekler buradan geçer)                    │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐       ┌───────────────┐
│   TOPLAMA     │      │   ANALİZ      │       │   MOTOR       │
│   SERVİSLERİ  │      │   SERVİSLERİ  │       │   SERVİSLERİ  │
├───────────────┤      ├───────────────┤       ├───────────────┤
│ Market        │      │ Technical     │       │ Decision      │
│ KAP           │      │ Fundamental   │       │ Portfolio     │
│ News          │      │ Sentiment     │       │ Risk          │
│ Macro         │      │ Sector        │       │ Compliance    │
│ TEFAS         │      │               │       │ Backtest      │
└───────────────┘      └───────────────┘       └───────────────┘
```

## 📊 Veri Akışı

```
Piyasa Verileri → Toplama → Analiz → Kanıt Birleştirme → Karar → Portföy
      │              │          │            │              │         │
      ▼              ▼          ▼            ▼              ▼         ▼
   BIST API      PostgreSQL  20+ Göstergeler  Decision     Risk    Gerçek
   KAP API       Redis       LLM Çıkarımı    Engine      Check   İşlem
   RSS Feed                   Vector DB                   Email   Bildirim
```

## 🔑 Temel Kavramlar

### Portföy
Kullanıcının hisse senedi yatırımlarını temsil eden bir koleksiyondur. Her portföy:
- Benzersiz bir ID'ye sahiptir
- Bir kullanıcıya aittir
- Hisse senedi pozisyonlarını içerir
- Risk bütçesi ve pozisyon limitleri tanımlanabilir

### Karar (Decision)
Decision Engine'ın ürettiği trading önerisidir. İçerir:
- **Hisse Senedi** (ticker)
- **Aksiyon** (BUY, SELL, HOLD, REDUCE)
- **Güven Skoru** (0-1 arası)
- **Pozisyon Büyüklüğü** (%)
- **Kanıtlar** (analiz sonuçları)

### Kanıt (Evidence)
Her karar, farklı analiz kaynaklarından gelen kanıtlara dayanır:
- Teknik sinyaller
- Temel analiz sonuçları
- Duygu analizi
- Sektör karşılaştırması
- Makro göstergeler

## 🚀 Nasıl Başlarım?

### 1. Kurulum
Detaylı kurulum için [Deployment Rehberi](developer/deployment.md) sayfasını inceleyin.

### 2. API'ye Erişim
Sistem, REST API üzerinden erişilebilir. Tüm endpointler için [API Referansı](developer/api-reference.md) sayfasını ziyaret edin.

### 3. Portföy Oluşturma
```http
POST /api/v1/portfolios
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "My Portfolio",
  "base_currency": "TRY",
  "risk_budget_pct": 0.03,
  "max_position_pct": 0.25
}
```

### 4. Karar Takibi
```http
GET /api/v1/portfolios/{portfolio_id}/decisions
```

## 📁 Dokümantasyon Yapısı

| Klasör | İçerik |
|--------|--------|
| `user/` | Kullanıcı kılavuzları |
| `developer/` | Geliştirici dokümantasyonu |
| `reference/api/` | API detaylı referans |
| `reference/services/` | Servis bazlı dokümantasyon |
| `reference/infrastructure/` | Altyapı dokümantasyonu |

## ❓ Yardım

- **SSS**: [Sıkça Sorulan Sorular](user/faq.md)
- **Sorun Giderme**: [Troubleshooting Guide](developer/deployment.md#troubleshooting)
- **API Sorunları**: [API Reference](reference/api/README.md)

## 🔗 Hızlı Linkler

- [Portföy Yönetimi](user/portfolio-management.md)
- [Karar Sistemi](user/decision-system.md)
- [Analiz Servisleri](developer/services.md)
- [Veritabanı Şemaları](developer/database.md)
