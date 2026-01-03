import re
from typing import List


def _match_regex(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_regex(d, path, ov) for d in doc]):
            return True

        if not isinstance(doc, str):
            return False

        flags = re.NOFLAG
        if "i" in ov["$options"]:
            flags = flags | re.IGNORECASE
        if "m" in ov["$options"]:
            flags = flags | re.MULTILINE
        if "s" in ov["$options"]:
            flags = flags | re.DOTALL
        if "x" in ov["$options"]:
            flags = flags | re.VERBOSE

        matcher = re.compile(ov["$regex"], flags)

        if matcher.search(doc):
            return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_regex(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_regex(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_regex(d, path, ov) for d in doc])

    return False
