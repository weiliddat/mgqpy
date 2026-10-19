import re
from typing import NamedTuple


class _Regex(NamedTuple):
    literal: str | re.Pattern
    matcher: re.Pattern


# Plain ints: RegexFlag arithmetic costs microseconds per operation. The masks
# keep RegexFlag's inversion, which on Python 3.11+ covers only defined flags.
_OPTION_FLAGS = {"i": int(re.I), "m": int(re.M), "s": int(re.S), "x": int(re.X), "u": 0}
_UNSUPPORTED = int(~(re.IGNORECASE | re.MULTILINE | re.DOTALL | re.VERBOSE | re.UNICODE | re.ASCII))
_NOT_UNICODE = int(~re.UNICODE)


def _compile_regex(pattern, options=""):
    if not isinstance(options, str) or any(option not in _OPTION_FLAGS for option in options):
        raise ValueError("$options must contain only i, m, s, x, or u")
    literal = pattern
    flags = 0
    if isinstance(pattern, re.Pattern):
        if options:
            raise ValueError("options cannot be set in both a compiled regex and $options")
        if pattern.flags & _UNSUPPORTED:
            raise ValueError("unsupported compiled regex flags")
        flags |= pattern.flags & _NOT_UNICODE
        pattern = pattern.pattern
    if not isinstance(pattern, str):
        raise TypeError("regex pattern must be a string or a compiled string regex")
    if "\0" in pattern:
        raise ValueError("regex pattern must not contain a NUL character")
    for option in options:
        flags |= _OPTION_FLAGS[option]
    try:
        return _Regex(literal, re.compile(pattern, flags))
    except re.error as error:
        raise ValueError(f"unsupported or malformed regex: {error}") from error


def _match_regex(value, operand) -> bool:
    return isinstance(value, str) and operand.matcher.search(value)
