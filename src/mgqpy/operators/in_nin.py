from mgqpy.operators.eq_ne_not import _match_eq
from mgqpy.utils import is_array_index

from typing import List


def _match_in(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list):
            for d in doc:
                if _match_in(d, path, ov):
                    return True

        for o in ov:
            if _match_eq(doc, path, o):
                return True
        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_in(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_in(doc[idx], rest, ov)

    if isinstance(doc, list):
        for d in doc:
            if _match_in(d, path, ov):
                return True
        return False

    if None in ov:
        return True

    return False


def _match_nin(doc, path: List[str], ov) -> bool:
    return not _match_in(doc, path, ov)
