import logging
import re
import time
import uuid
from urllib.parse import parse_qsl

from django.conf import settings

from .logging import request_id_var

logger = logging.getLogger("api.request")

# An incoming X-Request-ID is only trusted if it is short and harmless.
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
# Query parameters whose value must never reach the log.
_SENSITIVE = re.compile(
    r"token|pass|secret|key|auth|credential|session|jwt|refresh|access|signature",
    re.IGNORECASE,
)
_MAX_LOGGED = 300


def _printable(text: str) -> str:
    """Escape control and separator characters (newlines, ESC, U+2028 ...) so
    a crafted URL cannot forge or split log lines. Bangla/emoji stay readable."""
    escaped = "".join(
        ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii")
        for ch in text
    )
    return escaped if len(escaped) <= _MAX_LOGGED else escaped[:_MAX_LOGGED] + "..."


def _safe_query(query_string: str) -> str:
    if not query_string:
        return ""
    parts = []
    for key, value in parse_qsl(query_string, keep_blank_values=True):
        parts.append(f"{key}=***" if _SENSITIVE.search(key) else f"{key}={value}")
    return "?" + "&".join(parts)


class RequestLoggingMiddleware:
    """One log line per request: method, path, status and duration.

        GET /api/todos?status=pending 200 12.4ms

    Never logs request bodies or headers. Sets an X-Request-ID response header
    (reusing a valid incoming one) that is also attached to every log line.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500  # what we report if the exception escapes every layer
        try:
            response = self.get_response(request)
            status = response.status_code
            response["X-Request-ID"] = request_id
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            try:
                self._log(request, status, elapsed_ms)
            finally:
                request_id_var.reset(token)

    def _log(self, request, status, elapsed_ms):
        target = _printable(request.path + _safe_query(request.META.get("QUERY_STRING", "")))
        message = f"{_printable(request.method)} {target} {status} {elapsed_ms:.1f}ms"

        noisy = request.path == "/api/health" or request.path.startswith(settings.STATIC_URL_PREFIX)
        if status >= 500:
            logger.error(message)
        elif status >= 400:
            logger.warning(message)
        elif noisy:
            logger.debug(message)  # health checks and static files: hidden at INFO
        elif elapsed_ms >= settings.SLOW_REQUEST_MS:
            logger.warning("SLOW %s", message)
        else:
            logger.info(message)