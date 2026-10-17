import operator
from itertools import zip_longest
from typing import List

from mgqpy.utils import coerce, in_same_type_bracket, is_array_index


def _match_lt(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if type(doc) in (int, float) and type(ov) in (int, float):
            return doc < ov

        if isinstance(doc, list):
            for d in doc:
                if _match_lt(d, path, ov):
                    return True

        if isinstance(doc, list) and isinstance(ov, list):
            if doc < ov:
                return True

        if isinstance(doc, dict) and isinstance(ov, dict):
            if not doc and not ov:
                return False

            keys = zip_longest(doc.keys(), ov.keys())
            for doc_key, ov_key in keys:
                if doc_key is None:
                    return True
                if ov_key is None:
                    return False
                if doc_key != ov_key:
                    return doc_key < ov_key
                if doc_key == ov_key:
                    if doc[doc_key] > ov[ov_key]:
                        return False
                    if doc[doc_key] < ov[ov_key]:
                        return True
            return False

        doc, ov = coerce(doc, ov)
        return in_same_type_bracket(doc, ov) and operator.lt(doc, ov)

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_lt(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_lt(doc[idx], rest, ov)

    if isinstance(doc, list):
        for d in doc:
            if _match_lt(d, path, ov):
                return True

    return False
