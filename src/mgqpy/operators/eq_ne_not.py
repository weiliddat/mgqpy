from typing import List

from mgqpy.operators.regex import _Regex
from mgqpy.utils import coerce, is_array_index

import mgqpy


# Eager loops avoid comprehension closure cells on every scalar call (Python 3.10/3.11).
def _match_eq(doc, path: List[str], ov) -> bool:
    if not path:
        if isinstance(doc, list):
            results = []
            for d in doc:
                results.append(_match_eq(d, path, ov))
            if any(results):
                return True

        if isinstance(ov, _Regex):
            if isinstance(doc, str):
                return bool(ov.matcher.search(doc))
            ov = ov.literal

        doc, ov = coerce(doc, ov)
        return doc == ov

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_eq(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_eq(doc[idx], rest, ov)

    if isinstance(doc, list):
        results = []
        for d in doc:
            results.append(_match_eq(d, path, ov))
        return any(results)

    if ov is None:
        return True

    return False


def _match_ne(doc, path: List[str], ov) -> bool:
    return not _match_eq(doc, path, ov)


def _match_not(doc, path, ov):
    return not mgqpy._match_cond({path: ov}, doc)
