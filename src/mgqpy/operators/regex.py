import re
from typing import NamedTuple


class _Regex(NamedTuple):
    literal: str | re.Pattern
    matcher: re.Pattern


def _compile_regex(pattern, options=""):
    if not isinstance(options, str) or any(option not in "imsxu" for option in options):
        raise ValueError("$options must contain only i, m, s, x, or u")
    literal = pattern
    flags = 0
    if isinstance(pattern, re.Pattern):
        if options:
            raise ValueError("options cannot be set in both a compiled regex and $options")
        allowed = re.IGNORECASE | re.MULTILINE | re.DOTALL | re.VERBOSE | re.UNICODE | re.ASCII
        if pattern.flags & ~allowed:
            raise ValueError("unsupported compiled regex flags")
        flags |= pattern.flags & ~re.UNICODE
        pattern = pattern.pattern
    if not isinstance(pattern, str):
        raise TypeError("regex pattern must be a string or a compiled string regex")
    if "\0" in pattern:
        raise ValueError("regex pattern must not contain a NUL character")
    for option, flag in (("i", re.I), ("m", re.M), ("s", re.S), ("x", re.X)):
        if option in options:
            flags |= flag
    try:
        return _Regex(literal, re.compile(pattern, flags))
    except re.error as error:
        raise ValueError(f"unsupported or malformed regex: {error}") from error


def _match_regex(value, operand) -> bool:
    return isinstance(value, str) and operand.matcher.search(value)
