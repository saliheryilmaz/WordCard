# 🃏 WordCard — Kişisel Anki

Django tabanlı, SM-2 spaced repetition algoritmalı kelime öğrenme uygulaması.

---

## 🚀 Lokalde Başlatma (Windows)

```bash
# 1. Projeyi aç
cd wordcard

# 2. Sanal ortam kur (yoksa)
python -m venv venv
venv\Scripts\activate

# 3. Bağımlılıkları kur
pip install django

# 4. Veritabanını oluştur
python manage.py migrate

# 5. Admin kullanıcı oluştur (isteğe bağlı)
python manage.py createsuperuser

# 6. Çalıştır
python manage.py runserver
```

Tarayıcıda → http://127.0.0.1:8000

---

## ☁️ PythonAnywhere Deploy

### 1. GitHub'a push et
```bash
git init
git add .
git commit -m "initial wordcard"
git remote add origin https://github.com/kullanicin/wordcard.git
git push -u origin main
```

### 2. PythonAnywhere'de
```bash
git clone https://github.com/kullanicin/wordcard.git
cd wordcard
pip install --user django mysqlclient
python manage.py migrate
python manage.py collectstatic
```

### 3. settings.py'de güncelle
```python
DEBUG = False
ALLOWED_HOSTS = ['kullaniciadin.pythonanywhere.com']

# MySQL veritabanı bölümünü uncomment et, bilgileri gir
```

### 4. WSGI dosyası (PythonAnywhere web tab)
```python
import sys
sys.path.insert(0, '/home/kullaniciadin/wordcard')
os.environ['DJANGO_SETTINGS_MODULE'] = 'wordcard.settings'
```

---

## ⚙️ SM-2 Algoritması Nasıl Çalışır?

| Rating | Anlamı | Sonuç |
|--------|--------|-------|
| 😵 Hiç bilmedim | Tamamen yanlış | Başa dön, 1 gün |
| 😅 Zor | Güçlükle hatırladım | Kısa aralık |
| 🙂 İyi | Normal hatırladım | Standart aralık |
| 😎 Kolay | Hemen hatırladım | Uzun aralık |

Bir kelimeyi doğru hatırladıkça aralık uzar:
`1 gün → 6 gün → 14 gün → 30 gün → ...`

---

## ⌨️ Klavye Kısayolları

| Tuş | Eylem |
|-----|-------|
| `Space` | Kartı çevir |
| `1` | Hiç bilmedim |
| `2` | Zor |
| `3` | İyi |
| `4` | Kolay |

---

## 📁 Proje Yapısı

```
wordcard/
├── manage.py
├── requirements.txt
├── wordcard/           ← Django projesi
│   ├── settings.py
│   └── urls.py
└── flashcards/         ← Uygulama
    ├── models.py       ← Word + ReviewLog + SM-2
    ├── views.py        ← Tüm view'lar
    ├── forms.py
    ├── urls.py
    ├── admin.py
    └── templates/
        └── flashcards/
            ├── base.html
            ├── dashboard.html
            ├── review.html        ← Flashcard deneyimi
            ├── review_done.html
            ├── word_list.html
            ├── add_word.html
            └── auth.html
```
