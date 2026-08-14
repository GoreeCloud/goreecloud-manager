"""Django settings for GoreeCloud Manager.

The initial configuration intentionally favors a small, understandable monolith.
Environment-specific values are read from process environment variables or approved
file-backed secret mounts so reusable credentials never need to live in source control.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DEVELOPMENT_SECRET_KEY = "unsafe-development-key-change-me"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_non_negative_int(name: str, default: int = 0) -> int:
    """Read a non-negative integer and fail closed on invalid deployment input."""

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be a non-negative integer.") from exc

    if value < 0:
        raise ImproperlyConfigured(f"{name} must be a non-negative integer.")
    return value


def env_positive_float(
    name: str,
    default: float,
    *,
    maximum: float | None = None,
) -> float:
    """Read a finite positive float and reject unsafe deployment bounds."""

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        value = float(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be a positive finite number.") from exc

    if not math.isfinite(value) or value <= 0:
        raise ImproperlyConfigured(f"{name} must be a positive finite number.")
    if maximum is not None and value > maximum:
        raise ImproperlyConfigured(f"{name} must be no greater than {maximum:g} seconds.")
    return value


def env_secret(
    value_name: str,
    file_name: str,
    *,
    default: str | None = None,
) -> str:
    """Read one secret from either a direct environment value or a file, never both."""

    direct_value = os.getenv(value_name, "").strip()
    secret_file = os.getenv(file_name, "").strip()

    if direct_value and secret_file:
        raise ImproperlyConfigured(
            f"Set only one of {value_name} or {file_name}; file-backed secrets are preferred for deployment."
        )

    if secret_file:
        try:
            file_value = Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(
                f"Could not read the configured {file_name} secret file."
            ) from exc
        if not file_value:
            raise ImproperlyConfigured(f"The configured {file_name} secret file is empty.")
        return file_value

    if direct_value:
        return direct_value

    if default is not None:
        return default

    raise ImproperlyConfigured(f"Configure {value_name} or {file_name}.")


DEBUG = env_bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env_secret(
    "DJANGO_SECRET_KEY",
    "DJANGO_SECRET_KEY_FILE",
    default=DEFAULT_DEVELOPMENT_SECRET_KEY,
)
if not DEBUG and SECRET_KEY == DEFAULT_DEVELOPMENT_SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE must provide a non-development secret when DJANGO_DEBUG is false."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Adapter-specific network calls retain their own timeouts. This tighter Manager-level
# response budget prevents one slow or wedged adapter from holding the administrative
# request open indefinitely. The upper bound stays below the Gunicorn hard timeout.
MANAGER_INTEGRATION_BUDGET_SECONDS = env_positive_float(
    "MANAGER_INTEGRATION_BUDGET_SECONDS",
    7.0,
    maximum=20.0,
)

# Manager currently uses SQLite for its small private administrative workload. Give
# short-lived writes enough time to ride out brief lock contention without allowing a
# database wait to consume the full Gunicorn request deadline. Django's IMMEDIATE mode
# makes explicit transactions acquire their write intent up front and honor this timeout.
SQLITE_BUSY_TIMEOUT_SECONDS = env_positive_float(
    "DJANGO_SQLITE_TIMEOUT_SECONDS",
    10.0,
    maximum=20.0,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "goreecloud_manager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "goreecloud_manager.wsgi.application"

DATABASE_PATH = os.getenv("DJANGO_DB_PATH")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(DATABASE_PATH) if DATABASE_PATH else BASE_DIR / "db.sqlite3",
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "timeout": SQLITE_BUSY_TIMEOUT_SECONDS,
            "transaction_mode": "IMMEDIATE",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "overview"
LOGOUT_REDIRECT_URL = "login"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "manager": {
            "format": "%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
        }
    },
    "handlers": {
        "manager_console": {
            "class": "logging.StreamHandler",
            "formatter": "manager",
        }
    },
    "loggers": {
        "core.views": {
            "handlers": ["manager_console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.middleware": {
            "handlers": ["manager_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Production publication terminates HTTPS at Caddy. Trust only the conventional
# X-Forwarded-Proto value supplied by that controlled reverse-proxy boundary.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Keep HTTPS redirect/HSTS deployment-controlled until the final private Caddy path is
# approved. This preserves current loopback validation while allowing CI and future
# production to fail closed against Django's deployment security checks.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env_non_negative_int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)

# Docker checks Manager directly over loopback. These minimal operational endpoints
# remain available on the internal backend even when browser traffic is HTTPS-only.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$", r"^readyz/$"]
