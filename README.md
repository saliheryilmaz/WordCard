# 🃏 WordCard

> Django tabanlı, **SM-2 Spaced Repetition** algoritmalı akıllı kelime öğrenme uygulaması.

---

## ✨ Özellikler

### 📚 Kelime Yönetimi
- Kelime ekleme, düzenleme ve silme
- Her kelime için **İngilizce / Türkçe** çeviri
- Örnek cümle ve kişisel not alanları
- Eş anlamlılar (synonyms) desteği — virgülle ayrılmış liste

### 🧠 SM-2 Spaced Repetition Algoritması
- Bilimsel tabanlı aralıklı tekrar sistemi
- Kelime başına **tekrar sayısı, aralık ve ease factor** takibi
- 4 seviyeli öğrenme durumu: `Yeni → Öğreniliyor → Tekrar → Öğrenildi`
- Her oturumda sadece günü gelmiş kelimeler gösterilir

### 🔁 Flashcard Tekrar Sistemi
- Kartı çevirerek cevabı görme
- 4 farklı performans derecelendirmesi: **Hiç bilmedim / Zor / Orta / Kolay**
- Her derecelendirme sonrası bir sonraki tekrar tarihi otomatik hesaplanır
- Tüm tekrar geçmişi `ReviewLog` ile kaydedilir

### 🤖 AI Destekli Yardım
- **Cümle kontrolü** — yazdığın cümleyi AI değerlendirir ve geri bildirim verir
- **Örnek cümle üretme** — seçilen kelime için otomatik örnek cümle
- **Eş anlamlı getirme** — kelimeye ait synonyms listesini AI ile doldur

### 🗣️ Günlük İngilizce Pratik Sayfası
- Her gün değişen **konuşma konuları** ile AI destekli sohbet pratiği
- **Yazma egzersizi** bölümü — yazılarını AI değerlendirir ve puanlar
- Konuşma ve yazma becerilerini geliştirmeye odaklı interaktif arayüz

### 📊 Dashboard
- Toplam kelime sayısı ve öğrenme istatistikleri
- Bugün tekrar edilecek kelime sayısı
- Seviye bazlı dağılım özeti

### 🔐 Kullanıcı Sistemi
- Kayıt, giriş ve çıkış
- Her kullanıcı yalnızca kendi kelimelerini görür
- Oturum bazlı güvenli veri izolasyonu
