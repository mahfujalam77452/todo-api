"""Query-parameter helpers shared by list endpoints.

DRF's OrderingFilter silently ignores unknown fields and django-filter's
boolean widget silently ignores unknown values. For an API that is how typos
go unnoticed, so everything here answers 400 with a message instead.
"""
import re
import unicodedata

from django.db.models import F
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from .fields import StrictDateTimeField, ensure_in_year_window

_ID = re.compile(r"[1-9][0-9]{0,17}")  # ASCII digits only, no leading zero, fits int64
_TERM = re.compile(r"-?[a-z_]{1,40}")


# In a URL a "+" means a space, so ...T10:00:00+06:00 arrives as "...T10:00:00 06:00".
# Only a space *after* a complete time can be such a mangled "+".
_MANGLED_OFFSET = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?) (\d{2}(?::?\d{2})?)$"
)


MAX_ORDERING_LENGTH = 200
MAX_SEARCH_LENGTH = 100
MAX_SEARCH_TERMS = 10


def parse_id(raw, name):
    raw = raw.strip()
    if not _ID.fullmatch(raw):
        raise ValidationError(
            {name: [f"{name} must be a positive whole number. "
                    f"To pass several, repeat the parameter: ?{name}=1&{name}=2."]}
        )
    return int(raw)


def parse_bool(raw, name):
    value = raw.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValidationError({name: [f"{name} must be true or false."]})

def parse_datetime_param(raw, name, *, min_year, max_year):
    """A full ISO-8601 date and time (same rules as the due_date field)."""
    raw = _MANGLED_OFFSET.sub(r"\1+\2", raw.strip())
    try:
        value = StrictDateTimeField().run_validation(raw)
        ensure_in_year_window(value, min_year, max_year)
    except ValidationError as exc:
        raise ValidationError({name: exc.detail})
    return value
    
class StrictOrderingFilter(OrderingFilter):
    """?ordering=-priority,title

    - only the fields listed in the view's `ordering_fields` are allowed, no
      relation traversal; anything else, blank items and repeated fields are a 400
    - the view may map a field to a custom expression via `ordering_expressions`
      ({"title": lambda descending: ...}), e.g. case-insensitive or NULLS LAST
    - `id` is always appended as the last sort key so pages never shuffle
    - no ?ordering= means: keep the model's default ordering
    """

    def get_terms(self, request, view):
        raw = request.query_params.get(self.ordering_param)
        if raw is None or raw.strip() == "":
            return []
        raw = raw.strip()
        allowed = list(getattr(view, "ordering_fields", []))
        shown = ", ".join(allowed)

        def error(message):
            return ValidationError({self.ordering_param: [message]})

        if len(raw) > MAX_ORDERING_LENGTH:
            raise error("ordering is too long.")
        terms = [part.strip() for part in raw.split(",")]
        seen = set()
        for term in terms:
            name = term[1:] if term.startswith("-") else term
            if not _TERM.fullmatch(term) or name not in allowed:
                raise error(
                    f"Cannot order by '{term[:40]}'. Allowed: {shown} "
                    f"(prefix a field with - for descending order)."
                )
            if name in seen:
                raise error(f"'{name}' is listed more than once.")
            seen.add(name)
        return terms

    def filter_queryset(self, request, queryset, view):
        terms = self.get_terms(request, view)
        if not terms:
            return queryset
        expressions = getattr(view, "ordering_expressions", {})
        ordered = []
        for term in terms:
            descending = term.startswith("-")
            name = term.lstrip("-")
            build = expressions.get(name)
            if build:
                ordered.append(build(descending))
            else:
                ordered.append(F(name).desc() if descending else F(name).asc())
        # Tie-breaker follows the direction of the first key.
        ordered.append(F("id").desc() if terms[0].startswith("-") else F("id").asc())
        return queryset.order_by(*ordered)


class StrictSearchFilter(SearchFilter):
    """?search=milk  (case-insensitive, partial match)

    Several words must all match, each in at least one search field. Words are
    separated by spaces or commas; "double quotes" keep a phrase together.
    On top of DRF: text is NFC-normalised like the stored data, empty words
    are dropped, and the length and number of words are limited.
    """

    def get_search_terms(self, request):
        raw = request.query_params.get(self.search_param, "")
        if len(raw.strip()) > MAX_SEARCH_LENGTH:
            raise ValidationError(
                {self.search_param: [f"search must be at most {MAX_SEARCH_LENGTH} characters."]}
            )
        try:
            terms = super().get_search_terms(request)
        except ValidationError as exc:  # e.g. a null character
            raise ValidationError({self.search_param: exc.detail})
        terms = [unicodedata.normalize("NFC", term) for term in terms if term.strip()]
        if len(terms) > MAX_SEARCH_TERMS:
            raise ValidationError(
                {self.search_param: [f"search can have at most {MAX_SEARCH_TERMS} words."]}
            )
        return terms