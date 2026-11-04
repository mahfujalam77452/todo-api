from rest_framework import serializers


class StrictCharField(serializers.CharField):
    """CharField that only accepts JSON strings.

    DRF's CharField silently converts numbers (5.5 -> "5.5"); for names and
    titles that hides client bugs, so we reject anything that is not a string.
    """

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")  # "Not a valid string."
        return super().to_internal_value(data)