# Bildirimler

Finance AI V3, portföyünüz ve kararlarla ilgili çeşitli bildirimler gönderir. Bu dokümantasyon, bildirimlerin nasıl yapılandırılacağını açıklar.

## 📋 İçindekiler

1. [Bildirim Türleri](#bildirim-türleri)
2. [Alert Seviyeleri](#alert-seviyeleri)
3. [Bildirim Ayarları](#bildirim-ayarları)
4. [E-posta Bildirimleri](#e-posta-bildirimleri)
5. [Bildirim Geçmişi](#bildirim-geçmişi)

---

## Bildirim Türleri

### Karar Bildirimleri

| Tip | Açıklama | Örnek |
|-----|----------|-------|
| `DECISION_NEW` | Yeni karar oluşturuldu | "THYAO için ALIM kararı" |
| `DECISION_UPDATED` | Karar güncellendi | "THYAO kararı güven artışı" |
| `DECISION_BLOCKED` | Karar reddedildi | "THYAO kararı uyumluluk reddi" |

### Piyasa Bildirimleri

| Tip | Açıklama | Örnek |
|-----|----------|-------|
| `PRICE_ALERT` | Fiyat hedefe ulaştı | "GARAN 10 TL'yi geçti" |
| `VOLUME_SPIKE` | Hacim anomalisi | "ASELS hacmi %50 arttı" |
| `INDEX_MOVE` | Endeks değişimi | "XU100 %2 düştü" |

### Portföy Bildirimleri

| Tip | Açıklama | Örnek |
|-----|----------|-------|
| `REBALANCE_NEEDED` | Rebalancing gerekli | "THYAO ağırlığı %22'yi aştı" |
| `RISK_ALERT` | Risk limiti yaklaşıyor | "Portföy VaR %80'e ulaştı" |
| `POSITION_LIMIT` | Pozisyon limiti ihlali | "Tek hisse %25'i aştı" |

### Sistem Bildirimleri

| Tip | Açıklama | Örnek |
|-----|----------|-------|
| `SYSTEM_ERROR` | Sistem hatası | "Veri toplama servisi hatası" |
| `MAINTENANCE` | Bakım duyurusu | "Sistem bakımı 02:00-04:00" |

---

## Alert Seviyeleri

| Seviye | Renk | Açıklama | Örnek |
|--------|------|----------|-------|
| **INFO** | Mavi | Bilgilendirme | Yeni karar oluşturuldu |
| **WARN** | Sarı | Uyarı | Rebalance önerisi |
| **CRITICAL** | Kırmızı | Kritik | Risk limiti aşıldı |
| **EMERGENCY** | Mor | Acil | Sistem çökmesi |

---

## Bildirim Ayarları

### Mevcut Ayarları Görme

```bash
GET /api/v1/notifications/settings
Authorization: Bearer <token>
```

### Bildirim Ayarlarını Güncelleme

```bash
PUT /api/v1/notifications/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "email_enabled": true,
  "push_enabled": false,
  "min_grade": "WARN",
  "tickers": ["THYAO", "GARAN", "ASELS"],
  "portfolio_ids": ["123e4567-e89b-12d3-a456-426614174000"],
  "notification_types": ["DECISION_NEW", "REBALANCE_NEEDED", "RISK_ALERT"]
}
```

### Parametreler

| Parametre | Tip | Açıklama | Varsayılan |
|-----------|-----|----------|------------|
| `email_enabled` | boolean | E-posta bildirimleri | `true` |
| `push_enabled` | boolean | Push bildirimleri | `false` |
| `min_grade` | string | Minimum alert seviyesi | `INFO` |
| `tickers` | array | Takip edilecek hisseler | Tümü |
| `portfolio_ids` | array | Takip edilecek portföyler | Tümü |
| `notification_types` | array | Bildirim türleri | Tümü |

---

## E-posta Bildirimleri

### E-posta Bildirimlerini Aktifleştirme

1. **Ayarlar** sayfasına gidin
2. **E-posta Bildirimleri** seçin
3. **Aktifleştir** seçin
4. Minimum seviye belirleyin
5. Kaydet'e tıklayın

### E-posta Formatı

```
Konu: [Finance AI V3] THYAO - ALIM Kararı Oluşturuldu

Finance AI V3 - Karar Bildirimi
═══════════════════════════════════

Ticker: THYAO
Portföy: Ana Portföy
Karar: ALIM
Güven: %75
Hisse Sayısı: 350
Tahmini Değer: 63,175 TL

Aksiyon Nedeni:
THYAO için GÜÇLÜ ALIM önerisi. Sinyal gücü: POZITIF.
Kanıt sayısı: 5, Çelişki skoru: %12

Bu bir yatırım tavsiyesi DEĞİLDİR.
Yatırım kararlarınızı kendi araştırmanızla destekleyiniz.

═══════════════════════════════════
Finance AI V3 - Otonom Finansal Analist
```

---

## Bildirim Geçmişi

### Tüm Bildirimleri Listeleme

```bash
GET /api/v1/notifications
Authorization: Bearer <token>
```

### Filtreleme

```bash
# Okunmamış bildirimler
GET /api/v1/notifications?is_read=false
Authorization: Bearer <token>

# Belirli bir portföy
GET /api/v1/notifications?portfolio_id={id}
Authorization: Bearer <token>

# Kritik bildirimler
GET /api/v1/notifications?grade=CRITICAL
Authorization: Bearer <token>
```

### Bildirimi Okundu İşaretleme

```bash
PATCH /api/v1/notifications/{notification_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "is_read": true
}
```

### Tümünü Okundu İşaretleme

```bash
PATCH /api/v1/notifications/mark-all-read
Authorization: Bearer <token>
```

---

## Bildirim Tercihleri API

### Portfolio Bazlı Bildirimler

```bash
# Portföy bildirim ayarlarını getir
GET /api/v1/portfolios/{portfolio_id}/notification-settings

# Portföy bildirim ayarlarını güncelle
PUT /api/v1/portfolios/{portfolio_id}/notification-settings
Content-Type: application/json

{
  "decision_alerts": true,
  "rebalance_alerts": true,
  "risk_alerts": true,
  "min_confidence": 0.6
}
```

---

## Test Bildirimi Gönderme

### Test E-postası

```bash
POST /api/v1/notifications/test-email
Authorization: Bearer <token>
```

### Test Bildirimi

```bash
POST /api/v1/notifications/test
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "DECISION_NEW",
  "grade": "INFO"
}
```

---

## Push Bildirimleri

### Web Push Ayarları

Tarayıcınızda bildirim almak için:

1. Dashboard'da oturum açın
2. Ayarlar > Bildirimler > Push
3. "İzin Ver" seçin

### Bildirim Gönderme URL'i (n8n Entegrasyonu)

Sistemin push bildirimlerini kullanmak için:

```
POST /api/v1/notifications/push
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Yeni Karar",
  "body": "THYAO için ALIM kararı oluşturuldu",
  "data": {
    "type": "DECISION_NEW",
    "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
    "ticker": "THYAO"
  }
}
```

---

## SSS

### Bildirim almıyorum, ne yapmalıyım?

1. E-posta adresinizi doğrulayın
2. Spam klasörünü kontrol edin
3. Bildirim ayarlarınızı kontrol edin
4. Minimum seviyenin doğru olduğundan emin olun

### Bildirim sıklığını nasıl ayarlarım?

Şu anda dakika başına bildirim gönderilir. Yoğun bildirim alıyorsanız, `min_grade` seviyesini yükseltin.

### Belirli hisseler için bildirim alabilir miyim?

Evet, `tickers` parametresi ile sadece belirli hisseleri takip edebilirsiniz.
