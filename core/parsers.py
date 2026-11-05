from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class SafeJSONParser(JSONParser):
    """JSONParser that turns absurdly deep nesting into a 400.

    Python's json module raises RecursionError for something like
    '[[[[...' (100 000 levels, only ~100 KB), which DRF does not catch, so the
    client would get a 500.
    """

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError:
            raise ParseError("JSON is nested too deeply.")