# Karar Sistemi

Finance AI V3'ün karar mekanizması, birden fazla analiz kaynağından gelen verileri birleştirerek trading kararları üretir.

## 📋 İçindekiler

1. [Karar Mekanizması Nasıl Çalışır?](#karar-mekanizması-nasıl-çalışır)
2. [Kanıt Kaynakları](#kanıt-kaynakları)
3. [Kanıt Ağırlıklandırma](#kanıt-ağırlıklandırma)
4. [Karar Tipleri](#karar-tipleri)
5. [Güven Skoru](#güven-skoru)
6. [Karar Ömrü](#karar-ömrü)

---

## Karar Mekanizması Nasıl Çalışır?

```
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Engine                               │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Technical    │    │ Fundamental  │    │ Sentiment    │       │
│  │ Analysis     │    │ Analysis     │    │ Analysis     │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                    │                    │               │
│         └────────────────────┼────────────────────┘               │
│                              ▼                                    │
│                    ┌──────────────────┐                           │
│                    │  Evidence        │                           │
│                    │  Aggregation     │                           │
│                    │                  │                           │
│                    │  • Ağırlıklandırma                        │
│                    │  • Normalizasyon │                           │
│                    │  • Çelişki kontrolü                        │
│                    └────────┬─────────┘                           │
│                             ▼                                     │
│                    ┌──────────────────┐                           │
│                    │  Confidence      │                           │
│                    │  Calculation     │                           │
│                    └────────┬─────────┘                           │
│                             ▼                                     │
│                    ┌──────────────────┐                           │
│                    │  Action          │                           │
│                    │  Decision        │                           │
│                    │  BUY/SELL/HOLD   │                           │
│                    └──────────────────┘                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Kanıt Kaynakları

Sistem beş farklı kaynaktan kanıt toplar:

### 1. Teknik Analiz

| Gösterge | Sinyal |
|----------|--------|
| RSI | Aşırı alım (>70) / Aşırı satım (<30) |
| MACD | Pozitif/Negatif kesişim |
| Bollinger | Band dışı kırılım |
| SMA | Fiyat SMA üstünde/altında |
| Volume | Hacim artışı/azalışı |

**Ağırlık**: 0.25 (varsayılan)

### 2. Temel Analiz

KAP açıklamalarından çıkarılan:
- FAVÖK değişimi
- Net kar değişimi
- Borç/Öz kaynak oranı
- Karşılaştırmalı sektör oranları

**Ağırlık**: 0.25 (varsayılan)

### 3. Duygu Analizi

Haber ve açıklamalardan:
- Pozitif/Negatif/Neutral duygu skoru
- İkna düzeyi (conviction)

**Ağırlık**: 0.15 (varsayılan)

### 4. Sektör Analizi

- Sektörün genel performansı
- Sektör içi karşılaştırma
- Sektör momentumu

**Ağırlık**: 0.15 (varsayılan)

### 5. Makro Göstergeler

- TCMB politikası
- Enflasyon verileri
- Döviz kurları
- Büyüme göstergeleri

**Ağırlık**: 0.20 (varsayılan)

---

## Kanıt Ağırlıklandırma

### Varsayılan Ağırlıklar

```python
DEFAULT_WEIGHTS = {
    "technical": 0.25,
    "fundamental": 0.25,
    "sentiment": 0.15,
    "sector": 0.15,
    "macro": 0.20
}
```

### Ağırlık Ağırlaştırma Formülü

```
Weighted Signal = Σ (weight_i × signal_i × strength_i × confidence_i) / Σ weight_i
```

| Değişken | Açıklama |
|----------|----------|
| `weight` | Kaynak ağırlığı |
| `signal` | Sinyal değeri (-1, 0, +1) |
| `strength` | Sinyal gücü (0-1) |
| `confidence` | Analiz güveni (0-1) |

---

## Karar Tipleri

| Karar | Koşul | Açıklama |
|-------|-------|----------|
| **BUY** | Weighted Signal > 0.5, Confidence > 0.7 | Güçlü alım sinyali |
| **HOLD** | Orta sinyal, düşük güven | Mevcut durumu koru |
| **SELL** | Weighted Signal < -0.5, Confidence > 0.7 | Güçlü satım sinyali |
| **REDUCE** | Orta bearish, yüksek pozisyon | Pozisyonu azalt |
| **INSUFFICIENT_EVIDENCE** | Confidence < threshold | Yetersiz veri |

### Karar Matrisi

```
                    Düşük Güven          Yüksek Güven
                   ┌─────────────┬─────────────┐
   Güçlü Bullish   │   HOLD     │    BUY      │
   (WS > 0.5)      │            │  (WS>0.7)   │
                   ├─────────────┼─────────────┤
   Nötr            │   HOLD     │    HOLD     │
   (-0.2<WS<0.2)  │            │             │
                   ├─────────────┼─────────────┤
   Güçlü Bearish   │   HOLD     │    SELL     │
   (WS < -0.5)     │            │  (WS<-0.7)  │
                   └─────────────┴─────────────┘
```

---

## Güven Skoru

Güven skoru (0-1), kararın ne kadar güvenilir olduğunu gösterir.

### Hesaplama Formülü

```
Confidence = (evidence_factor × 0.4) + (signal_factor × 0.4) + (consistency_factor × 0.2)
```

| Faktör | Açıklama |
|--------|----------|
| `evidence_factor` | Kanıt sayısı / 5 (maks 5 kaynak) |
| `signal_factor` | Mutlak weighted signal değeri |
| `consistency_factor` | 1 - contradiction_score |

### Güven Seviyeleri

| Skor | Seviye | Anlamı |
|------|--------|--------|
| 0.0 - 0.3 | Düşük | Çok dikkatli olunmalı |
| 0.3 - 0.6 | Orta | Normal ihtiyat |
| 0.6 - 0.8 | Yüksek | Güvenle izlenebilir |
| 0.8 - 1.0 | Çok Yüksek | Güçlü sinyal |

---

## Karar Ömrü

### Karar Döngüsü

```
1. Karar Üretildi
       │
       ▼
2. Compliance Kontrolü ────► REDUKSE EDİLDİ (BLOCKED)
       │                              │
       │ (APPROVED)                   │
       ▼                              │
3. Uygulama / Bekletme                    │
       │                                 │
       ▼                                 │
4. 24 saat sonra yeniden değerlendirme     │
       │
       ▼
5. Yeni karar üretilir veya mevcut korunur
```

### Otomatik Yeniden Değerlendirme

- Sistem her 24 saatte bir kararları otomatik olarak yeniden değerlendirir
- Piyasa koşulları değişirse karar güncellenir
- Mevcut bir karar, yeni kanıtlarla çelişirse uyarı üretilir

---

## Karar Detayını İnceleme

### API İsteği

```bash
GET /api/v1/portfolios/{portfolio_id}/decisions/{decision_id}
Authorization: Bearer <token>
```

### Örnek Yanıt

```json
{
  "decision_id": "550e8400-e29b-41d4-a716-446655440000",
  "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
  "ticker": "THYAO",
  "action": "BUY",
  "confidence": 0.75,
  "position_size_pct": 0.15,
  "evidence_count": 5,
  "contradiction_score": 0.12,
  "supervisor_reasoning": "THYAO için GÜÇLÜ ALIM önerisi. Sinyal gücü: POZITIF. Güven: %75, Kanıt sayısı: 5, Çelişki skoru: %12.",
  "effective_at": "2024-01-15T10:30:00Z",
  "data_completeness": "complete",
  "compliance_status": "APPROVED",
  "evidence": [
    {
      "stream": "technical",
      "signal": "BULLISH",
      "strength": 0.85,
      "confidence": 0.80
    },
    {
      "stream": "fundamental",
      "signal": "BULLISH",
      "strength": 0.70,
      "confidence": 0.75
    }
  ]
}
```

---

## Uyumluluk Kontrolü (Compliance)

Her karar, uygulamaya alınmadan önce Compliance Agent tarafından kontrol edilir:

### Kontrol Edilenler

1. **Yasaklı Dil**: Karar metninde yasadışı veya etik dışı ifadeler
2. **Feragatname**: Zorunlu feragatnamenin bulunması
3. **Kanıt Atfı**: Tüm kanıtların kaynağının belirtilmesi
4. **Güven Aralığı**: Güven skorunun geçerli aralıkta olması
5. **Pozisyon Kısıtlamaları**: Pozisyon büyüklüğü limitleri

### Compliance Durumları

| Durum | Açıklama |
|-------|----------|
| `PENDING` | Kontrol bekliyor |
| `APPROVED` | Kontrol geçti |
| `BLOCKED` | Kontrol başarısız, uygulanmadı |

---

## ⚠️ Önemli Uyarılar

> **BU BİR YATIRIM TAVSİYESİ DEĞİLDİR**
> 
> Finance AI V3 tarafından üretilen kararlar **yatırım tavsiyesi niteliğinde değildir**.
> 
> Karar kullanmadan önce:
> 1. Kendi analizinizi yapın
> 2. Risk toleransınızı değerlendirin
> 3. Profesyonel danışmanlık alın

---

## Sonraki Adımlar

- [Bildirimler](notifications.md) - Karar bildirimlerini ayarlama
- [Risk Yönetimi](risk-management.md) - Risk metriklerini anlama
