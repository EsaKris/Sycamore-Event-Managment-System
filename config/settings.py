"""
Django settings for the SEMS (Sycamore Event Management System) project.
"""

from pathlib import Path

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core / Security
# ---------------------------------------------------------------------------
DEBUG = config('DEBUG', default=True, cast=bool)

_INSECURE_DEFAULT_KEY = 'django-insecure-change-me-in-production'
SECRET_KEY = config('SECRET_KEY', default=_INSECURE_DEFAULT_KEY)
if not DEBUG and SECRET_KEY == _INSECURE_DEFAULT_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY is still the insecure default. Set a real SECRET_KEY in '
        'the environment before running with DEBUG=False.'
    )

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# --- Transport & cookie hardening -------------------------------------------------
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=8 * 60 * 60, cast=int)  # 8 hours

SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=not DEBUG, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0 if DEBUG else 31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'


USE_X_FORWARDED_HOST = config('USE_X_FORWARDED_HOST', default=False, cast=bool)
if config('BEHIND_PROXY', default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


FILE_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024  # 8MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'corsheaders',

    # SEMS apps
    'apps.core',
    'apps.accounts',
    'apps.people',
    'apps.events',
    'apps.departments',
    'apps.registrations',
    'apps.attendance',
    'apps.followup',
    'apps.campaigns',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.AuditLogMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------------
# Database — DB_ENGINE picks the backend once DB_HOST is set:
# ---------------------------------------------------------------------------
DB_ENGINE = config('DB_ENGINE', default='postgresql').lower()

if config('DB_HOST', default='') and DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME', default='sems_db'),
            'USER': config('DB_USER', default='sems_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }
elif config('DB_HOST', default=''):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='sems_db'),
            'USER': config('DB_USER', default='sems_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST'),
            'PORT': config('DB_PORT', default='5432'),
            # Require TLS to the database in production; set DB_SSL_REQUIRE=False
            # only for a same-host/private-network Postgres with no TLS available.
            'OPTIONS': {'sslmode': config('DB_SSLMODE', default='prefer' if DEBUG else 'require')},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Staff login brute-force throttle (see apps/dashboard/views.py AdminLoginView).
LOGIN_THROTTLE_ATTEMPTS = config('LOGIN_THROTTLE_ATTEMPTS', default=5, cast=int)
LOGIN_THROTTLE_COOLDOWN_SECONDS = config('LOGIN_THROTTLE_COOLDOWN_SECONDS', default=15 * 60, cast=int)

LOGIN_URL = '/dashboard/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/dashboard/login/'

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='Africa/Lagos')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']


STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


SERVE_MEDIA_VIA_DJANGO = config('SERVE_MEDIA_VIA_DJANGO', default=False, cast=bool)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Cache — backs rate limiting (public registration throttle, staff login
# ---------------------------------------------------------------------------
REDIS_URL = config('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000,https://localhost:8000,https://127.0.0.1:8000',
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())

# ---------------------------------------------------------------------------
# SEMS-specific settings
# ---------------------------------------------------------------------------
SEMS_PERSON_ID_PREFIX = config('SEMS_PERSON_ID_PREFIX', default='SYC')
SEMS_PERSON_ID_DIGITS = config('SEMS_PERSON_ID_DIGITS', default=6, cast=int)

# ---------------------------------------------------------------------------
# Backups — apps/core/backups.py. A backup bundles both the database dump
# AND the media folder.
# ---------------------------------------------------------------------------
BACKUP_DIR = config('BACKUP_DIR', default=str(BASE_DIR / 'backups'))
BACKUP_RETENTION_COUNT = config('BACKUP_RETENTION_COUNT', default=14, cast=int)

# Optional — set BACKUP_S3_BUCKET to also upload every backup off-host.
BACKUP_S3_BUCKET = config('BACKUP_S3_BUCKET', default='')
BACKUP_S3_PREFIX = config('BACKUP_S3_PREFIX', default='sems-backups/')

# ---------------------------------------------------------------------------
# Email — Gmail / Google Workspace SMTP.
# ---------------------------------------------------------------------------
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

_default_email_backend = (
    'django.core.mail.backends.smtp.EmailBackend' if (not DEBUG or EMAIL_HOST_USER)
    else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_BACKEND = config('EMAIL_BACKEND', default=_default_email_backend)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'no-reply@sems.local')

if not DEBUG and EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend' and not EMAIL_HOST_USER:
    raise ImproperlyConfigured(
        'EMAIL_HOST_USER is not set. Configure Gmail/Workspace SMTP credentials '
        '(EMAIL_HOST_USER + EMAIL_HOST_PASSWORD, an App Password) before running '
        'with DEBUG=False, or registration/administrator emails will silently fail.'
    )


SEMS_SITE_URL = config('SEMS_SITE_URL', default='')

# ---------------------------------------------------------------------------
# hCaptcha — public registration forms (participant + worker/pastor).
# ---------------------------------------------------------------------------
HCAPTCHA_SITE_KEY = config('HCAPTCHA_SITE_KEY', default='')
HCAPTCHA_SECRET_KEY = config('HCAPTCHA_SECRET_KEY', default='')