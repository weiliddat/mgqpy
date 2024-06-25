from numbers import Number
from typing import List


def _match_size(doc, path: List[str], ov) -> bool:
    if not _validate_size(ov):
        return False

    if len(path) == 0:
        if not isinstance(doc, list):
            return False

        if len(doc) == int(ov):
            return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_size(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_size(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_size(d, path, ov) for d in doc])

    return False


def _validate_size(ov) -> bool:
    return isinstance(ov, Number)
