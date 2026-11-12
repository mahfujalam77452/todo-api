"""
Django settings for the TODO List REST API.

All environment-specific values come from environment variables
(loaded from a local `.env` file when present). See `.env.example`.
"""
import os
import sys
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url

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
def env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a whole number, got {raw!r}.") from None
    if value < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}, got {value}.")
    return value

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
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    # Local apps
    "core",
    "accounts",
    "teams",
    "categories",
    "todos",
    "notifications",
    "dashboard",

]

MIDDLEWARE = [
    "core.middleware.RequestLoggingMiddleware",  # first: times the whole request
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
# ------------------------------------------------------------------- database
# PostgreSQL in production, SQLite in local development.
SQLITE_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "db.sqlite3")).strip()
DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///" + SQLITE_PATH,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Custom user (email login). Must be set before the very first `migrate`.
AUTH_USER_MODEL = "accounts.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------------------- JWT
# JWT_SIGNING_KEY lets the token key differ from SECRET_KEY (rotate one without
# the other). Without it SECRET_KEY signs the tokens.
JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY", "").strip() or SECRET_KEY
if len(JWT_SIGNING_KEY) < 32:
    raise ImproperlyConfigured("JWT_SIGNING_KEY (or SECRET_KEY) must be at least 32 characters.")

SIMPLE_JWT = {
    # Short-lived access token: it cannot be revoked, so it must expire quickly.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    # Every refresh gives a new refresh token and revokes the old one, so a
    # stolen refresh token stops working as soon as the owner uses theirs.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ---------------------------------------------------------------------- cache
# With REDIS_URL set (e.g. redis://localhost:6379/1) the cache is Redis, shared
# by every worker and surviving restarts. Without it a per-process in-memory
# cache is used, so the project runs fine without Redis during development.
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL and not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    raise ImproperlyConfigured(
        "REDIS_URL must start with redis://, rediss:// or unix:// "
        f"(got {REDIS_URL.split('@')[-1][:30]!r})."  # never print a password
    )

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "todoapp",  # lets several apps share one Redis
            "TIMEOUT": 300,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                # We only cache JSON-friendly data. The default (pickle) would let
                # anyone who can write to Redis run code in this app.
                "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
                # Redis is an optimisation: if it is down, the API keeps working
                # (a cache miss) instead of returning 500s.
                "IGNORE_EXCEPTIONS": True,
                # ...and must fail fast, not hang every request.
                "SOCKET_CONNECT_TIMEOUT": 0.5,
                "SOCKET_TIMEOUT": 0.5,
                "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "todoapp",
        }
    }

# When django-redis swallows an error (Redis down) it logs it here; the line is
# rate-limited in LOGGING, so an outage is visible without flooding the log.
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = "api.cache"

CATEGORY_CACHE_SECONDS = 300  # upper bound for stale data if an invalidation is missed

# ----------------------------------------------------------------- validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("email", "name")},
    },
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

# ----------------------------------------------------------------- rate limiting
# How many reverse proxies / load balancers sit between the internet and this
# app. Requests are counted per client IP, and the IP comes from REMOTE_ADDR.
# With 0 (the default) the X-Forwarded-For header is ignored, which is right
# when the app is reached directly: otherwise anybody could send a different
# X-Forwarded-For with every request and never hit a limit (DRF's own default
# trusts the whole header). Behind one proxy set NUM_PROXIES=1, and so on.
NUM_PROXIES = env_int("NUM_PROXIES", 0)

# The counters live in the cache: Redis when REDIS_URL is set (shared by every
# worker), otherwise memory (each worker counts on its own, so with N workers
# the real limit is up to N times higher). If Redis is down, limits stop being
# enforced rather than the API failing.
THROTTLE_RATES = {
    "anon": "20/min",       # unauthenticated requests to endpoints without their own scope
    "user": "100/min",      # every signed-in user, counted per user, not per IP
    "login": "5/min",       # per IP: slows down password guessing
    "register": "5/hour",   # per IP: slows down account creation and email probing
    "token": "30/min",      # per IP: refresh and logout
    "notifications": "120/min",  # notification polling has its own budget
}


# ------------------------------------------------------------ Django REST Framework
REST_FRAMEWORK = {
    # JSON only: no browsable HTML API, and form/plain-text bodies get 415.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["core.parsers.SafeJSONParser"],
    # Auth is added in Phase 4 (JWT + IsAuthenticated by default).
    # Empty list now so no Session/Basic auth sneaks in (it would turn 401s into 403s).
        # Secure by default: every endpoint needs a valid JWT unless a view opts out
    # explicitly (register, login, refresh, logout, health). No Session/Basic
    # authentication, which would also turn 401 answers into 403.
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.SafeJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "core.exceptions.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        # ?limit=&offset= on list endpoints (categories opt out, see CategoryViewSet)
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardLimitOffsetPagination",
        # Rate limits (see THROTTLE_RATES above). Authentication and permissions run
    # first, so a 401 or 403 does not use up the caller's allowance.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": THROTTLE_RATES,
    "NUM_PROXIES": NUM_PROXIES,
    # ?status=... etc., defined per view in a FilterSet
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

# ---------------------------------------------------------------- API schema/docs
SPECTACULAR_SETTINGS = {
    "TITLE": "TODO List REST API",
    "DESCRIPTION": (
        "JWT-authenticated TODO API. Users can manage only their own todos; "
        "categories are globally readable and admin-managed."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "SERVE_PERMISSIONS": [],
    "AUTHENTICATION_WHITELIST": [
        "core.authentication.SafeJWTAuthentication",
    ],
    "SECURITY": [{"BearerAuth": []}],
    "TAGS": [
        {"name": "Authentication", "description": "Register and manage JWT tokens."},
        {"name": "Todos", "description": "Private todos owned by the authenticated user."},
        {"name": "Categories", "description": "Global categories; writes require admin permissions."},
        {"name": "System", "description": "Health and API documentation endpoints."},
    ],
}


# ------------------------------------------------------------------- logging
# Console by default (Docker/PaaS collect stdout). Set LOG_FILE to also write a
# rotating file (5 MB x 5). Every line carries the request id; see core/logging.py.
SLOW_REQUEST_MS = 1000  # a request this slow is logged as a WARNING

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "traceback_only": {"()": "core.logging.OnlyWithTraceback"},
        "once_a_minute": {"()": "core.logging.RateLimited", "seconds": 60},
    },
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
        # A broken Redis would log on every request; one line a minute is enough.
        "api.cache": {"level": "WARNING", "filters": ["once_a_minute"], "propagate": True},
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
            target.setdefault("handlers", []).append("file")