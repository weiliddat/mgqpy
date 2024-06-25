import math
from numbers import Number
from typing import List


def _match_mod(doc, path: List[str], ov) -> bool:
    if not _validate_mod(ov):
        return False

    if len(path) == 0:
        if isinstance(doc, list) and any([_match_mod(d, path, ov) for d in doc]):
            return True

        if not isinstance(doc, Number):
            return False

        divisor = math.floor(ov[0])
        expected_remainer = math.floor(ov[1])
        doc_remainer = math.floor(doc % divisor)

        return doc_remainer == expected_remainer

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_mod(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_mod(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_mod(d, path, ov) for d in doc])

    return False


def _validate_mod(ov):
    return (
        isinstance(ov, list)
        and len(ov) == 2
        and isinstance(ov[0], Number)
        and isinstance(ov[1], Number)
    )
