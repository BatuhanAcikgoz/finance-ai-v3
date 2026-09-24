# Sıkça Sorulan Sorular (SSS)

Finance AI V3 hakkında sıkça sorulan sorular ve cevapları.

## 📋 İçindekiler

1. [Genel Sorular](#genel-sorular)
2. [Portföy Yönetimi](#portföy-yönetimi)
3. [Kararlar ve Analiz](#kararlar-ve-analiz)
4. [Risk ve Performans](#risk-ve-performans)
5. [Teknik Sorunlar](#teknik-sorunlar)

---

## Genel Sorular

### Finance AI V3 nedir?

Finance AI V3, Türk sermaye piyasalarında (BIST) yatırım kararlarını desteklemek için tasarlanmış bir **Otonom Finansal Araştırma Analisti**dir. Piyasa verilerini toplar, teknik ve temel analiz yapar ve trading kararları üretir.

### Bu bir yatırım danışmanlığı mı?

**Hayır.** Finance AI V3 bir yatırım danışmanlığı hizmeti **değildir**. Sistem tarafından üretilen tüm kararlar, analizler ve öneriler bilgilendirme amaçlıdır. Herhangi bir yatırım kararı almadan önce kendi araştırmanızı yapmanız ve profesyonel danışmanlık almanız gerekmektedir.

### Hangi veri kaynaklarını kullanıyor?

- **BIST API**: Hisse senedi fiyatları ve işlem hacimleri
- **KAP**: Kamuyu Aydınlatma Platformu açıklamaları
- **Haber Kaynakları**: Bloomberg HT, TRT Haber, AA, Reuters
- **TCMB**: Merkez Bankası verileri
- **TÜİK**: Türkiye İstatistik Kurumu verileri

### Sistem hangi saatlerde çalışıyor?

Sistem 7/24 çalışır ancak:
- **Piyasa verileri**: BIST çalışma saatlerinde (09:30-18:00 TRT)
- **Karar üretimi**: Piyasa açıkken daha sık, kapalıyken daha seyrek
- **Analizler**: Gece ve hafta sonları da çalışır

---

## Portföy Yönetimi

### Portföy oluştururken nelere dikkat etmeliyim?

1. **Para Birimi**: TRY, USD veya EUR seçebilirsiniz
2. **Risk Bütçesi**: Yıllık maksimum kayıp oranınızı belirleyin (varsayılan: %3)
3. **Pozisyon Limiti**: Tek hisse senedinin maksimum ağırlığı (varsayılan: %25)
4. **Sektör Limiti**: Tek sektörün maksimum ağırlığı (varsayılan: %40)

### Birden fazla portföy oluşturabilir miyim?

Evet, sınırsız sayıda portföy oluşturabilirsiniz. Her portföyün:
- Kendi risk profili olabilir
- Farklı hisse senedi listesi olabilir
- Bağımsız kararlar üretilir

### Portföyümde olmayan hisseler için karar alınabilir mi?

Hayır. Sistem sadece portföyünüzde tanımlı hisseleri analiz eder ve karar üretir.

### Mevcut portföyümü nasıl import edebilirim?

Şu anda CSV import özelliği bulunmamaktadır. API üzerinden pozisyonları tek tek eklemeniz gerekmektedir.

---

## Kararlar ve Analiz

### Karar güveni nedir ve nasıl yorumlanmalıdır?

Güven skoru (0-1), kararın ne kadar güvenilir olduğunu gösterir:

| Skor | Yorum |
|------|-------|
| 0.0-0.3 | Çok dikkatli olunmalı, ek doğrulama gerekli |
| 0.3-0.6 | Normal ihtiyat ile takip edilebilir |
| 0.6-0.8 | Güvenle izlenebilir |
| 0.8-1.0 | Güçlü sinyal, yüksek güven |

### Sistem neden "INSUFFICIENT_EVIDENCE" kararı veriyor?

Yeterli kanıt toplanamadığında bu karar verilir. Sebepleri:
- Hisse senedi için yeni veri yok
- Analiz servisleri geçici olarak çalışmıyor
- Tarihsel veri yetersiz (yeni listelenen hisseler)

### Kararlar ne sıklıkla güncellenir?

- **Piyasa açıkken**: Her 10-15 dakikada bir
- **Piyasa kapalıyken**: Saat başı
- **Gece**: Temel analiz ve güncellemeler

### Bir kararı manuel olarak değiştirebilir miyim?

Hayır, sistem kararlarını manuel olarak değiştiremez veya iptal edemezsiniz. Ancak:
- Bildirim ayarlarınızı değiştirebilirsiniz
- Kararı inceleyebilir ve kendi değerlendirmenizi yapabilirsiniz
- Pozisyonunuzu manuel olarak değiştirebilirsiniz

---

## Risk ve Performans

### VaR nedir?

Value at Risk (VaR), %95 güvenle 1 günde kaybedebileceğiniz maksimum tutarı gösterir. Örneğin, VaR 15,000 TL ise, %95 ihtimalle 1 günde 15,000 TL'den fazla kaybetmezsiniz.

### CVaR ile VaR arasındaki fark nedir?

- **VaR**: Kaybın maksimumu
- **CVaR (Conditional VaR)**: VaR aşıldığında ortalama kayıp

CVaR, "en kötü senaryoda ne kadar kaybedebilirim" sorusunun cevabını verir.

### Beta nedir?

Beta, portföyünüzün piyasaya karşı duyarlılığını gösterir:
- Beta = 1: Piyasa ile aynı hareket
- Beta > 1: Piyasadan daha volatil
- Beta < 1: Piyasadan daha az volatil

### Performans raporlarını nereden görebilirim?

```bash
GET /api/v1/portfolios/{portfolio_id}/performance
```

Dashboard üzerinden de performans grafiğini inceleyebilirsiniz.

---

## Teknik Sorunlar

### API'ye erişemiyorum, ne yapmalıyım?

1. **Token süresi dolmuş olabilir**: Yeniden giriş yapın
2. **Sunucu yanıt vermiyor**: Sistem bakımda olabilir
3. **Bağlantı hatası**: İnternet bağlantınızı kontrol edin

### "Rate limit exceeded" hatası alıyorum

API istek sınırı aşıldı. Bekleyin veya:
- Premium plan için iletişime geçin
- Batch isteklerini kullanın

### Bildirim almıyorum

1. E-posta adresinizi doğrulayın
2. Spam klasörünü kontrol edin
3. Bildirim ayarlarınızı kontrol edin
4. Minimum seviyenin doğru olduğundan emin olun

### Sistem yanlış veri gösteriyor

BIST verilerinde gecikeme olabilir. Gerçek zamanlı veri için BIST API'ye doğrudan bakmanızı öneririz.

### Şifremi unuttum

Yöneticinizle veya sistem destek ekibiyle iletişime geçin.自助密码重置功能目前不可用。

---

## Destek

Yukarıdaki cevaplarda bulamadığınız sorular için:

- **E-posta**: support@example.com
- **GitHub Issues**: [Proje Sayfası](https://github.com/your-org/FinanceAutomations)
- **Docs**: [Dokümantasyon](https://docs.example.com)
