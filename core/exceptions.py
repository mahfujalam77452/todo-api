"""One error format for the whole API.

    {"error": "<readable message>", "code": <http status>}

Validation errors (400) add a "details" object with every problem per field:

    {"error": "title: This field is required.", "code": 400,
     "details": {"title": ["This field is required."]}}

Anything that is not an API error (a bug, a database failure) becomes a generic
500 {"error": "Internal server error", "code": 500}: the real exception, with
its traceback, goes to the log and never to the client.
"""
import logging

from django.core.exceptions import RequestDataTooBig, SuspiciousOperation
from django.db import IntegrityError, OperationalError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

logger = logging.getLogger("api.errors")

NON_FIELD = api_settings.NON_FIELD_ERRORS_KEY  # "non_field_errors"


def _flatten(detail, prefix=""):
    """Yield (field path, message) pairs from any shape DRF can produce.

    A ValidationError detail can be a dict, a list of messages, a dict of
    lists, a dict of dicts (nested serializers) or a list of dicts
    (many=True). Paths look like "title" or "items.0.name".
    """
    if isinstance(detail, dict):
        for key, value in detail.items():
            yield from _flatten(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(detail, (list, tuple)):
        for index, item in enumerate(detail):
            if isinstance(item, (dict, list, tuple)):
                yield from _flatten(item, f"{prefix}.{index}" if prefix else str(index))
            else:
                yield (prefix or NON_FIELD, str(item))
    else:
        yield (prefix or NON_FIELD, str(detail))


def _validation_body(exc, status_code):
    details = {}
    pairs = list(_flatten(exc.detail))
    for path, message in pairs:
        details.setdefault(path, []).append(message)

    if not pairs:
        summary = "Validation failed."
    else:
        path, message = pairs[0]
        summary = message if path == NON_FIELD else f"{path}: {message}"
        if len(pairs) > 1:
            summary += f" (and {len(pairs) - 1} more)"
    return {"error": summary, "code": status_code, "details": details}


def _message(data):
    """A single readable message from the data DRF built for an API error.

    `data` is {"detail": "..."} for most errors; simplejwt adds "code" and
    "messages" next to "detail". Reading the response data (instead of the
    exception) also covers Django's Http404/PermissionDenied, which DRF
    converts into its own exceptions.
    """
    if isinstance(data, dict):
        data = data.get("detail", " ".join(str(v) for v in data.values()) or "Request failed.")
    if isinstance(data, (list, tuple)):
        data = " ".join(str(item) for item in data)
    return str(data)


def exception_handler(exc, context):
    """DRF EXCEPTION_HANDLER. It must never raise: if our own formatting code
    fails, the client still gets the generic JSON 500."""
    try:
        return _handle(exc, context)
    except Exception:
        logger.exception("The error handler itself failed")
        return _error_response(500, "Internal server error")


def _handle(exc, context):
    # Too-large bodies are raised by Django while DRF reads the request.
    if isinstance(exc, RequestDataTooBig):
        exc = _PayloadTooLarge()
    elif isinstance(exc, SuspiciousOperation):
        exc = exceptions.ParseError("Bad request.")

    response = drf_exception_handler(exc, context)
    if response is None:
        return _unhandled(exc, context)  # not an API error

    if isinstance(exc, exceptions.ValidationError):
        response.data = _validation_body(exc, response.status_code)
    else:
        response.data = {"error": _message(response.data), "code": response.status_code}
    return response


def _error_response(status_code, message, headers=None):
    return Response({"error": message, "code": status_code}, status=status_code, headers=headers)


def _safe_str(exc):
    try:
        return str(exc)
    except Exception:  # an exception whose __str__ is broken
        return ""


def _where(context):
    request = (context or {}).get("request")
    if request is None:
        return "unknown request"
    return f"{request.method} {request.path}"  # never the body or query string


def _unhandled(exc, context):
    """Turn a non-API exception into a JSON response; log the real cause."""
    set_rollback()  # undo the transaction if ATOMIC_REQUESTS is ever enabled
    where = _where(context)
    info = (type(exc), exc, exc.__traceback__)

    if isinstance(exc, OperationalError) and "locked" in _safe_str(exc).lower():
        # SQLite: another writer held the lock longer than the timeout.
        logger.warning("Database busy during %s", where, exc_info=info)
        return _error_response(
            503, "The service is busy. Please retry shortly.", headers={"Retry-After": "2"}
        )

    if isinstance(exc, IntegrityError):
        # Validation should have caught it; a race or a missing check got through.
        logger.error("Integrity error during %s", where, exc_info=info)
        return _error_response(409, "The request conflicts with existing data.")

    logger.error("Unhandled exception during %s", where, exc_info=info)
    return _error_response(500, "Internal server error")


class _PayloadTooLarge(exceptions.APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request body is too large."
    default_code = "payload_too_large"


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current resource state."
    default_code = "conflict"