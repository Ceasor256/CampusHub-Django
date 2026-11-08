"""
CampusHub settings.

Everything environment-specific comes from environment variables (see
.env.example). Defaults are safe for local development only.
"""

import os
from pathlib import Path

import dj_database_url
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal .env support (KEY=VALUE lines). Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-insecure-key-change-me" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
APP_URL = env("APP_URL", "http://localhost:8010")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "accounts",
    "marketplace",
    "gigs",
    "deals",
    "messaging",
    "payments",
    "staff",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "core.middleware.LastSeenMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csp",
                "core.context_processors.site",
            ],
            "builtins": ["core.templatetags.ui", "django.contrib.humanize.templatetags.humanize"],
        },
    }
]

# ------------------------------------------------------------------ database
# DATABASE_URL (PostgreSQL) in production; SQLite file for local development.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(env("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ auth
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60  # 1 hour

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ------------------------------------------------------------------ i18n / locale
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]  # architecture ready for Luganda/Swahili via gettext
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------ static & media
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", BASE_DIR / "media"))
STORAGES = {
    # Production: switch "default" to S3-compatible storage (django-storages) via env.
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# ------------------------------------------------------------------ email
# "console" stores mail in the dev outbox (/dev/outbox/). Production: SMTP or provider.
EMAIL_BACKEND = env("EMAIL_BACKEND", "core.mail.OutboxBackend")
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", "CampusHub <no-reply@campushub.ug>")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

# ------------------------------------------------------------------ cache (rate limiting)
# LocMem is per-process. Use Redis (REDIS_URL) when running several workers.
CACHES = (
    {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
    if env("REDIS_URL")
    else {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)

# ------------------------------------------------------------------ payments (Phase 2)
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", "test")
PAYMENT_WEBHOOK_SECRET = env("PAYMENT_WEBHOOK_SECRET", "dev-secret")

# ------------------------------------------------------------------ security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
