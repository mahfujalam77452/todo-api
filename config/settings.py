"""
Django settings for the TODO List REST API.

All environment-specific values come from environment variables
(loaded from a local `.env` file when present). See `.env.example`.
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Django 5.2 needs Python 3.10+. Fail early with a clear message.
if sys.version_info < (3, 10):
    raise RuntimeError("Python 3.10 or newer is required.")

BASE_DIR = Path(__file__).resolve().parent.parent

# Real environment variables always win over values in `.env`
# (load_dotenv does not override by default) -> works the same in Docker/CI.
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------- env helpers
def env_str(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value.strip() == "":
        raise ImproperlyConfigured(
            f"Environment variable {name} is required. "
            f"Copy .env.example to .env and set it."
        )
    return value.strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean (true/false), got {raw!r}.")


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ------------------------------------------------------------------- security
# No insecure fallback: the app refuses to start without a real SECRET_KEY.
SECRET_KEY = env_str("SECRET_KEY")

# Safe default is False; DEBUG must be switched on explicitly.
DEBUG = env_bool("DEBUG", default=False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
if not DEBUG and not ALLOWED_HOSTS:
    # Otherwise every request would silently fail with 400 Bad Request.
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be set (comma separated) when DEBUG is false."
    )


# ---------------------------------------------------------------- application
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "django_filters",
    # Local apps
    "core",
    "accounts",
    "categories",
    "todos",
]

MIDDLEWARE = [
    "core.middleware.RequestLoggingMiddleware",  # first: times the whole request
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ------------------------------------------------------------------- database
# SQLite. (Connection tuning + custom user model are done in Task 1.2.)
# SQLite, tuned for a web app that may run several workers.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            # Wait up to 20s for a lock instead of failing at once with
            # "database is locked".
            "timeout": 20,
            # WAL: readers don't block the writer (and vice versa).
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            # Take the write lock at BEGIN, so a transaction can't fail halfway
            # while upgrading from read to write lock.
            "transaction_mode": "IMMEDIATE",
        },
    }
}

# Custom user (email login). Must be set before the very first `migrate`.
AUTH_USER_MODEL = "accounts.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ----------------------------------------------------------------- validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# -------------------------------------------------------------- i18n / timezone
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"  # shown to API clients as +06:00
USE_I18N = True
USE_TZ = True  # stored as UTC in the database

STATIC_URL = "static/"
STATIC_URL_PREFIX = "/" + STATIC_URL.lstrip("/")  # used by the request log
STATIC_ROOT = BASE_DIR / "staticfiles"

# Reject request bodies bigger than this (judged by the Content-Length header).
# The largest valid todo is ~45 KB (10,000 characters x up to 4 bytes + title).
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
# ------------------------------------------------------------ Django REST Framework
REST_FRAMEWORK = {
    # JSON only: no browsable HTML API, and form/plain-text bodies get 415.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["core.parsers.SafeJSONParser"],
    # Auth is added in Phase 4 (JWT + IsAuthenticated by default).
    # Empty list now so no Session/Basic auth sneaks in (it would turn 401s into 403s).
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "EXCEPTION_HANDLER": "core.exceptions.exception_handler",
        # ?limit=&offset= on list endpoints (categories opt out, see CategoryViewSet)
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardLimitOffsetPagination",
    # ?status=... etc., defined per view in a FilterSet
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}


# ------------------------------------------------------------------- logging
# Console by default (Docker/PaaS collect stdout). Set LOG_FILE to also write a
# rotating file (5 MB x 5). Every line carries the request id; see core/logging.py.
SLOW_REQUEST_MS = 1000  # a request this slow is logged as a WARNING

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"traceback_only": {"()": "core.logging.OnlyWithTraceback"}},
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        # api.request: one line per request; api.errors: tracebacks of bugs
        "api": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # runserver's own access log repeats every request (with the raw query
        # string, tokens included); api.request already covers it.
        "django.server": {"handlers": ["console"], "level": "CRITICAL", "propagate": False},
        # Crashes outside DRF views (admin, middleware) with their traceback.
        # Everything else is already covered by api.request / api.errors.
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "filters": ["traceback_only"],
            "propagate": False,
        },
    },
}

LOG_FILE = os.environ.get("LOG_FILE", "").strip()
if LOG_FILE:
    try:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        open(LOG_FILE, "a", encoding="utf-8").close()  # is it writable?
    except OSError as exc:
        # A log file problem must not stop the API from starting.
        print(f"LOG_FILE ignored ({exc}); logging to the console only.", file=sys.stderr)
    else:
        LOGGING["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILE,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "standard",
        }
        for target in (LOGGING["root"], *LOGGING["loggers"].values()):
            target["handlers"].append("file")