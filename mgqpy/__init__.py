"""mongo query as a predicate function"""

__version__ = "0.1.10"

# Terminology
#
# Query refers to the document that is passed to the compiler / mongodb find that holds
#   the query conditions (can be multiple),
#   e.g. { "fruits.type": { "$eq": "berry", "$ne": "aggregate" }, "fruits": { "$size": 3 }}
#
# Cond (conditions) refers to a single path-expression pair,
#   e.g. { "fruits.type": { "$eq": "berry", "$ne": "aggregate" }
#
# Path refers to dot-separated fields,
#   e.g. "fruits.type"
#
# Exp (expression) refers to the object that holds operator and value pairs (can be multiple),
#   e.g. { "$eq": "berry", "$ne": "aggregate" }
#
# Op (operator) refers to the logical operator that is matched against the value,
#   e.g. "$eq"
#
# Ov (operator value) refers to the value that you are matching against in
#   the context of a single operator e.g. "berry"
#
# Doc refers to the object that is passed to the compiled filter function

import operator
from itertools import zip_longest
from numbers import Number
from typing import List

cmp_ops = {
    "$eq",
    "$gt",
    "$gte",
    "$in",
    "$lt",
    "$lte",
    "$ne",
    "$nin",
}


class Query:
    def __init__(self, query):
        self._query = query
        pass

    def match(self, doc) -> bool:
        results: List[bool] = []

        for path in self._query:
            exp_or_ov = self._query[path]
            is_all_ops = (
                exp_or_ov
                and isinstance(exp_or_ov, dict)
                and all(key in cmp_ops for key in exp_or_ov.keys())
            )

            path_parts = path.split(".")

            if is_all_ops:
                if "$eq" in exp_or_ov:
                    results.append(_match_eq(doc, path_parts, exp_or_ov["$eq"]))
                if "$gt" in exp_or_ov:
                    results.append(_match_gt(doc, path_parts, exp_or_ov["$gt"]))
                if "$gte" in exp_or_ov:
                    results.append(_match_gte(doc, path_parts, exp_or_ov["$gte"]))
                if "$lt" in exp_or_ov:
                    results.append(_match_lt(doc, path_parts, exp_or_ov["$lt"]))
                if "$lte" in exp_or_ov:
                    results.append(_match_lte(doc, path_parts, exp_or_ov["$lte"]))
            else:
                results.append(_match_eq(doc, path_parts, exp_or_ov))

        return all(results)


def _match_eq(doc: dict, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_eq(d, path, ov) for d in doc]):
            return True

        return doc == ov

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_eq(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_eq(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_eq(d, path, ov) for d in doc])

    if ov is None:
        return True

    return False


def _match_gt(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_gt(d, path, ov) for d in doc]):
            return True

        if isinstance(doc, list) and isinstance(ov, list):
            if doc > ov:
                return True

        if isinstance(doc, dict) and isinstance(ov, dict):
            keys = zip_longest(doc.keys(), ov.keys())
            for doc_key, ov_key in keys:
                if doc_key is None:
                    return False
                if ov_key is None:
                    return True
                if doc_key != ov_key:
                    return doc_key > ov_key
                if doc_key == ov_key:
                    if doc[doc_key] > ov[ov_key]:
                        return True
                    if doc[doc_key] < ov[ov_key]:
                        return False
            return False

        if isinstance(doc, Number) and isinstance(ov, Number):
            return operator.gt(doc, ov)

        if isinstance(doc, str) and isinstance(ov, str):
            return operator.gt(doc, ov)

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_gt(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_gt(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_gt(d, path, ov) for d in doc])

    return False


def _match_gte(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_gte(d, path, ov) for d in doc]):
            return True

        if isinstance(doc, list) and isinstance(ov, list):
            if doc >= ov:
                return True

        if isinstance(doc, dict) and isinstance(ov, dict):
            if not doc and not ov:
                return True

            keys = zip_longest(doc.keys(), ov.keys())
            for doc_key, ov_key in keys:
                if doc_key is None:
                    return False
                if ov_key is None:
                    return True
                if doc_key != ov_key:
                    return doc_key > ov_key
                if doc_key == ov_key:
                    if doc[doc_key] > ov[ov_key]:
                        return True
                    if doc[doc_key] < ov[ov_key]:
                        return False
            return True

        if isinstance(doc, Number) and isinstance(ov, Number):
            return operator.ge(doc, ov)

        if isinstance(doc, str) and isinstance(ov, str):
            return operator.ge(doc, ov)

        if doc is None and ov is None:
            return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_gte(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_gte(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_gte(d, path, ov) for d in doc])

    if ov is None:
        return True

    return False


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
            return operator.lt(doc, ov)

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

        if isinstance(doc, Number) and isinstance(ov, Number):
            return operator.le(doc, ov)

        if isinstance(doc, str) and isinstance(ov, str):
            return operator.le(doc, ov)

        if doc is None and ov is None:
            return True

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
