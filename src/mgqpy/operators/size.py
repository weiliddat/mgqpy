from typing import List

from mgqpy.utils import is_array_index, is_finite_number


def _match_size(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if not isinstance(doc, list):
            return False

        return len(doc) == ov

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_size(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_size(doc[idx], rest, ov)

    if isinstance(doc, list):
        for d in doc:
            if _match_size(d, path, ov):
                return True

    return False


def _validate_size(ov) -> bool:
    return is_finite_number(ov) and 0 <= ov <= 2**31 - 1 and ov == int(ov)
