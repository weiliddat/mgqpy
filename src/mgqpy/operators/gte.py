import operator
from itertools import zip_longest

from mgqpy.path import MISSING
from mgqpy.utils import coerce, in_same_type_bracket


def _match_gte(doc, ov) -> bool:
    if type(doc) in (int, float) and type(ov) in (int, float):
        return doc >= ov
    if isinstance(doc, dict) and isinstance(ov, dict):
        for doc_key, ov_key in zip_longest(doc, ov):
            if doc_key is None:
                return False
            if ov_key is None:
                return True
            if doc_key != ov_key:
                return doc_key > ov_key
            if doc[doc_key] > ov[ov_key]:
                return True
            if doc[doc_key] < ov[ov_key]:
                return False
        return True
    if doc is MISSING:
        return ov is None
    if doc is None and ov is None:
        return True
    doc, ov = coerce(doc, ov)
    return in_same_type_bracket(doc, ov) and bool(operator.ge(doc, ov))
