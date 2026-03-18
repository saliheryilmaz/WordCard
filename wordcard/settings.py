"""
WordCard - Django Settings
PythonAnywhere deployment ready.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# GÜVENLIK: Deploy ederken .env veya environment variable kullan
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-degistir-bunu-uretim-ortaminda')

# PythonAnywhere'de False yap ve ALLOWED_HOSTS'a ekle
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    # 'kullaniciadin.pythonanywhere.com',  # ← kendi adresini ekle
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'flashcards',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wordcard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wordcard.wsgi.application'

# --- VERİTABANI ---
# Geliştirme: SQLite (kolay)
# Üretim: MySQL (PythonAnywhere)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# MySQL için (PythonAnywhere'de uncomment et):
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'kullaniciadin$wordcard',
#         'USER': 'kullaniciadin',
#         'PASSWORD': 'sifren',
#         'HOST': 'kullaniciadin.mysql.pythonanywhere-services.com',
#         'PORT': '3306',
#         'OPTIONS': {'charset': 'utf8mb4'},
#     }
# }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Groq API — .env dosyasina koy veya environment variable olarak set et
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
