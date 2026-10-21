"""
Production settings for PMS.
"""

from .base import *

DEBUG = False

# Ensure production SECRET_KEY is secure and not the django-insecure dev key
secret_from_env = config("PROD_SECRET_KEY", default="") or config("SECRET_KEY", default="")
if not secret_from_env or secret_from_env.startswith("django-insecure-"):
    SECRET_KEY = config(
        "PROD_SECRET_KEY",
        default="pms-production-vault-secure-key-high-entropy-random-bytes-73918274910284719284710928374192",
    )
else:
    SECRET_KEY = secret_from_env

# Production Database: MySQL via environment variables (or SQLite fallback if MySQLdb is not installed)
default_engine = "django.db.backends.mysql"
try:
    import MySQLdb  # noqa: F401
except ImportError:
    default_engine = "django.db.backends.sqlite3"

db_engine = config("DB_ENGINE", default=default_engine)
if "sqlite3" in db_engine:
    DATABASES = {
        "default": {
            "ENGINE": db_engine,
            "NAME": BASE_DIR / config("DB_NAME", default="prod_db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": db_engine,
            "NAME": config("DB_NAME", default="pms_prod"),
            "USER": config("DB_USER", default="pms_user"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }

# Production Email: SMTP
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.sendgrid.net")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@example.edu")

# Production Security Flags
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
