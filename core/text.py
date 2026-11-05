"""Text cleaning for user-supplied strings (titles, names, descriptions)."""
import re
import unicodedata

# Invisible characters that str.strip() does not remove: zero-width space,
# byte-order mark, word joiner. They are removed from the *edges* only.
_EDGE = r"\s\u200b\ufeff\u2060"
_EDGE_RE = re.compile(rf"^[{_EDGE}]+|[{_EDGE}]+$")

# Characters that render as nothing but are not covered by the categories below
# (Braille blank, Hangul fillers, Khmer inherent vowels, Mongolian vowel sep.).
_BLANK_LOOKALIKES = set("\u2800\u3164\u115f\u1160\u17b4\u17b5\u180e\uffa0")
# control, format (zero-width etc.), spaces, line/paragraph separators,
# unassigned, private use, surrogates
_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Zs", "Zl", "Zp", "Cn", "Co", "Cs"}

# Bidirectional embedding/override/isolate controls: used to make text display
# differently from its stored order ("trojan source" style spoofing).
_BIDI_CONTROLS = set("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_ALLOWED_IN_MULTILINE = {"\n", "\r", "\t"}


class TextError(ValueError):
    """Raised with a `code` that matches an error message of the field."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def clean_text(value: str, *, single_line: bool) -> str:
    """Normalise `value` and reject characters that should not be stored.

    - NFC normalisation, so the same text typed on different devices is equal
      (matters for Bangla: "য়" can be one code point or two).
    - trims whitespace and zero-width characters at both ends
    - rejects control characters (line breaks/tabs are allowed only when
      `single_line` is False), line/paragraph separators in single-line text,
      and bidirectional override characters
    - text with no visible character at all (e.g. only zero-width spaces,
      Braille blank, Hangul filler) becomes "" so the caller can treat it as blank

    Zero-width joiners/non-joiners *inside* text are kept: Bangla conjuncts and
    emoji sequences need them.
    """
    text = _EDGE_RE.sub("", unicodedata.normalize("NFC", value))

    for ch in text:
        category = unicodedata.category(ch)
        if category == "Cc" and not (not single_line and ch in _ALLOWED_IN_MULTILINE):
            raise TextError("control_characters")
        if category in ("Zl", "Zp") and single_line:
            raise TextError("control_characters")
        if ch in _BIDI_CONTROLS:
            raise TextError("bidi_controls")

    if not any(
        unicodedata.category(ch) not in _INVISIBLE_CATEGORIES
        and ch not in _BLANK_LOOKALIKES
        for ch in text
    ):
        return ""
    return text