import re

from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

_DIGITS = re.compile(r"[0-9]+")  # ASCII only: int() would also accept "٣" or "১"
MAX_OFFSET = 2**53  # far beyond any real table; keeps offset+limit inside SQLite's int64


def _parse(request, name):
    """Return the int value of a query parameter, None if absent or blank."""
    raw = request.query_params.get(name)
    if raw is None or raw.strip() == "":
        return None
    raw = raw.strip()
    if not _DIGITS.fullmatch(raw):
        raise ValidationError({name: [f"{name} must be a non-negative integer."]})
    return int(raw)


class StandardLimitOffsetPagination(LimitOffsetPagination):
    """?limit=10&offset=20

    Unlike DRF's default, bad values are a 400 instead of being silently
    replaced by the default. A limit above max_limit is lowered to max_limit
    (the response always reports the limit that was actually used).
    """

    default_limit = 10
    max_limit = 100

    def get_limit(self, request):
        limit = _parse(request, self.limit_query_param)
        if limit is None:
            return self.default_limit
        if limit < 1:
            raise ValidationError({self.limit_query_param: ["limit must be at least 1."]})
        return min(limit, self.max_limit)

    def get_offset(self, request):
        offset = _parse(request, self.offset_query_param)
        if offset is None:
            return 0
        if offset > MAX_OFFSET:
            raise ValidationError({self.offset_query_param: ["offset is too large."]})
        return offset

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.count,
                "limit": self.limit,
                "offset": self.offset,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )