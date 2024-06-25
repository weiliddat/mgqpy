import operator
from itertools import zip_longest
from numbers import Number
from typing import List


def _match_lt(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_lt(d, path, ov) for d in doc]):
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

        if isinstance(doc, Number) and isinstance(ov, Number):
            return operator.lt(doc, ov)  # type: ignore

        if isinstance(doc, str) and isinstance(ov, str):
            return operator.lt(doc, ov)

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_lt(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_lt(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_lt(d, path, ov) for d in doc])

    return False
