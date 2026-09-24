# Kullanıcı Dokümantasyonu

Bu klasör, Finance AI V3 sistemini **kullanıcı** olarak nasıl kullanacağınızı açıklar.

## 📖 İçindekiler

### [Başlangıç Rehberi](getting-started.md)
Sistemi hızlıca tanıyın ve ilk adımlarınızı atın.

### [Portföy Yönetimi](portfolio-management.md)
- Portföy oluşturma
- Pozisyon ekleme/çıkarma
- Rebalancing
- Performans takibi

### [Karar Sistemi](decision-system.md)
- Trading kararları nasıl alınır?
- Karar güveni nedir?
- Kanıtlar nasıl değerlendirilir?
- Hangi aksiyonlar alınabilir?

### [Bildirimler](notifications.md)
- Alert türleri
- Bildirim ayarları
- E-posta bildirimleri

### [SSS](faq.md)
Sıkça sorulan sorular ve cevapları

## 🎯 Hedef Kitle

Bu dokümantasyon, aşağıdaki kullanıcılar için hazırlanmıştır:

- **Yatırımcılar**: Sistemin ürettiği kararları anlamak ve kullanmak isteyenler
- **Portföy Yöneticileri**: Birden fazla portföyü yöneten profesyoneller
- **Analistler**: Sistem tarafından üretilen analizleri inceleyenler

## ⚠️ Önemli Uyarı

> **BU BİR YATIRIM DANIŞMANLIĞI DEĞİLDİR**
> 
> Finance AI V3 tarafından üretilen tüm kararlar, analizler ve öneriler **yatırım tavsiyesi niteliğinde değildir**.
> 
> Herhangi bir yatırım kararı almadan önce:
> 1. Kendi araştırmanızı yapın
> 2. Risk toleransınızı değerlendirin
> 3. Profesyonel danışmanlık alın
> 
> Sistem tarafından üretilen hiçbir içerik, kaybınızdan dolayı sorumluluk kabul etmez.

## 🔐 Hesap ve Güvenlik

### Kimlik Doğrulama
Sisteme erişim için JWT token kullanılır. Token alma:

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "username": "kullanici_adi",
  "password": "sifre"
}
```

### Şifre Değiştirme
Şifrenizi değiştirmek için yöneticinizle iletişime geçin.

## 📊 Dashboard

Sistemin web arayüzü (dashboard) üzerinden:
- Portföy durumunuzu görebilirsiniz
- Kararları inceleyebilirsiniz
- Grafikleri izleyebilirsiniz
- Alert oluşturabilirsiniz

Dashboard URL: `http://localhost:3001` (geliştirme ortamı)

## 🆘 Destek

Teknik destek için:
- E-posta: support@example.com
- GitHub Issues: [Proje Sayfası](https://github.com/your-org/FinanceAutomations)

## 📱 Mobil Erişim

Sistem şu anda mobil uygulama sunmamaktadır. Mobil uyumlu web arayüzü üzerinden erişim sağlayabilirsiniz.
