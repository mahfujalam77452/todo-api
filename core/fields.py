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