import mgqpy
from mgqpy.utils import is_array_index

from typing import List


def _match_elem_match(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if not isinstance(doc, list):
            return False

        # MongoDB matches the query only against elements that are documents,
        # reading a nested list as a document keyed by index
        for d in doc:
            if isinstance(d, list):
                d = {str(i): v for i, v in enumerate(d)}
            if isinstance(d, dict) and mgqpy._match_cond(ov, d):
                return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_elem_match(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_elem_match(doc[idx], rest, ov)

    if isinstance(doc, list):
        for d in doc:
            if _match_elem_match(d, path, ov):
                return True

    return False
