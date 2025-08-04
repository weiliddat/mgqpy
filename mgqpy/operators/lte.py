import operator
from itertools import zip_longest
from numbers import Number
from typing import List

from mgqpy.utils import coerce


def _match_lte(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_lte(d, path, ov) for d in doc]):
            return True

        if isinstance(doc, list) and isinstance(ov, list):
            if doc <= ov:
                return True

        if isinstance(doc, dict) and isinstance(ov, dict):
            if not doc and not ov:
                return True

            keys = zip_longest(doc.keys(), ov.keys())
            for doc_key, ov_key in keys:
                if doc_key is None:
                    return True
                if ov_key is None:
                    return False
                if doc_key != ov_key:
                    return doc_key < ov_key
                if doc_key == ov_key:
                    if doc[doc_key] < ov[ov_key]:
                        return True
                    if doc[doc_key] > ov[ov_key]:
                        return False
            return True

        if doc is None and ov is None:
            return True

        try:
            doc, ov = coerce(doc, ov)
            return operator.le(doc, ov)
        except Exception:
            pass

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_lte(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_lte(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_lte(d, path, ov) for d in doc])

    if ov is None:
        return True

    return False
