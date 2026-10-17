import re
from typing import List, NamedTuple

from mgqpy.utils import is_array_index


class _Regex(NamedTuple):
    literal: str | re.Pattern
    matcher: re.Pattern


def _compile_regex(pattern, options=""):
    if not isinstance(options, str) or any(option not in "imsxu" for option in options):
        raise ValueError("$options must contain only i, m, s, x, or u")
    literal = pattern
    flags = re.ASCII
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


def _match_regex(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list):
            for d in doc:
                if _match_regex(d, path, ov):
                    return True

        if not isinstance(doc, str):
            return False

        return bool(ov.matcher.search(doc))

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_regex(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_regex(doc[idx], rest, ov)

    if isinstance(doc, list):
        for d in doc:
            if _match_regex(d, path, ov):
                return True

    return False
