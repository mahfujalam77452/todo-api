import re
from rest_framework import serializers
from .text import TextError, clean_text

class StrictCharField(serializers.CharField):
    """CharField for names, titles and descriptions.

    - accepts only JSON strings (DRF would turn 5.5 into "5.5")
    - NFC-normalises and trims, including zero-width characters at the edges
    - rejects control characters and bidi overrides; with `single_line=True`
      (titles, names) line breaks and tabs are rejected too
    - text that is only invisible characters counts as blank
    The cleaning happens *before* the length validators, so max_length counts
    the characters that will actually be stored.
    """

    default_error_messages = {
        "control_characters": "Control characters and line breaks are not allowed.",
        "bidi_controls": "Text direction override characters are not allowed.",
    }

    def __init__(self, *, single_line=False, **kwargs):
        self.single_line = single_line
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")  # "Not a valid string."
        value = super().to_internal_value(data)
        try:
            cleaned = clean_text(value, single_line=self.single_line)
        except TextError as exc:
            self.fail(exc.code)
        if cleaned == "" and not self.allow_blank:
            self.fail("blank")
        return cleaned


class StrictBooleanField(serializers.BooleanField):
    """BooleanField that only accepts JSON true/false.

    DRF's BooleanField also accepts "yes", "1", 1, "on", ... which hides
    client bugs, so anything that is not a real boolean is rejected.
    """

    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid", input=data)  # "Must be a valid boolean."
        return data


class StrictPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """Primary-key field that only accepts real JSON integers.

    Without this, 1.5 is silently truncated to 1 by the ORM and "1" is accepted
    as a string, so a client bug would attach the wrong object.
    """

    def run_validation(self, data=serializers.empty):
        # DRF treats "" as null for related fields; an empty string is a
        # client mistake, not "no category" (that is spelled null).
        if isinstance(data, str) and data == "":
            self.fail("incorrect_type", data_type="str")
        return super().run_validation(data)

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail("incorrect_type", data_type=type(data).__name__)
        if not 0 < data < 2**63:  # can never exist; also avoids SQLite overflow
            self.fail("does_not_exist", pk_value=data)
        return super().to_internal_value(data)

# YYYY-MM-DD[T| ]hh:mm[:ss[.ffffff]][Z|+hh:mm|+hhmm|+hh]  (ASCII only, whole string).
# Whether the date itself exists (Feb 30) is checked by DRF afterwards.
_DATETIME_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(:[0-9]{2}(\.[0-9]{1,6})?)?"
    r"(Z|[+-][0-9]{2}(:?[0-9]{2})?)?"
)


class StrictDateTimeField(serializers.DateTimeField):
    """DateTimeField that insists on an explicit date *and* time in ASCII.

    DRF would also accept a bare date ("2026-12-01" -> 00:00, so the todo
    would look overdue from the first minute of its due day), compact forms
    and non-ASCII digits. Anything else is parsed by DRF as usual; a value
    without an offset is read as the current time zone (Asia/Dhaka).
    """

    default_error_messages = {
        "format": "Use a full date and time, e.g. 2026-12-01T18:00:00+06:00.",
    }

    def to_internal_value(self, value):
        if (
            not isinstance(value, str)
            or not value.isascii()
            or not _DATETIME_PATTERN.fullmatch(value)
        ):
            self.fail("format")
        return super().to_internal_value(value)


class StrictIntegerChoiceField(serializers.ChoiceField):
    """Choice field for integer choices that accepts only real JSON integers.

    DRF's ChoiceField compares str(value), so "2" would be accepted for 2.
    """

    def __init__(self, choices, **kwargs):
        allowed = ", ".join(f"{value} ({label})" for value, label in choices)
        kwargs.setdefault(
            "error_messages", {"invalid_choice": f"Must be one of: {allowed}."}
        )
        super().__init__(choices=choices, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail("invalid_choice", input=data)
        return super().to_internal_value(data)