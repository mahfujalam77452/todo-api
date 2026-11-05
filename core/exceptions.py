"""One error format for the whole API.

    {"error": "<readable message>", "code": <http status>}

Validation errors (400) add a "details" object with every problem per field:

    {"error": "title: This field is required.", "code": 400,
     "details": {"title": ["This field is required."]}}
"""
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation
from rest_framework import exceptions, status
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler as drf_exception_handler

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
    # Too-large bodies are raised by Django while DRF reads the request.
    if isinstance(exc, RequestDataTooBig):
        exc = _PayloadTooLarge()
    elif isinstance(exc, SuspiciousOperation):
        exc = exceptions.ParseError("Bad request.")

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # not an API error; Task 2.3 turns it into a JSON 500

    if isinstance(exc, exceptions.ValidationError):
        response.data = _validation_body(exc, response.status_code)
    else:
        response.data = {"error": _message(response.data), "code": response.status_code}
    return response


class _PayloadTooLarge(exceptions.APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request body is too large."
    default_code = "payload_too_large"