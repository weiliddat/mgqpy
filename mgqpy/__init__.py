"""mongo query as a predicate function"""

__version__ = "0.3.1"

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
import re
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
    "$not",
    "$regex",
    "$options",
}

log_ops = {
    "$and",
    "$or",
    "$nor",
}


class Query:
    def __init__(self, query):
        self._query = query
        pass

    def match(self, doc) -> bool:
        return match_cond(self._query, doc)


def match_cond(query, doc):
    results: List[bool] = []

    for path in query:
        if isinstance(path, str) and path in log_ops:
            if path == "$and":
                for cond in query[path]:
                    results.append(match_cond(cond, doc))
            if path == "$or":
                results.append(any([match_cond(cond, doc) for cond in query[path]]))
            if path == "$nor":
                results.append(not any([match_cond(cond, doc) for cond in query[path]]))
        else:
            exp_or_ov = query[path]
            is_all_ops = (
                exp_or_ov
                and isinstance(exp_or_ov, dict)
                and all(key in cmp_ops for key in exp_or_ov.keys())
            )

            path_parts = path.split(".")

            if is_all_ops:
                if "$eq" in exp_or_ov:
                    results.append(_match_eq(doc, path_parts, exp_or_ov["$eq"]))
                if "$ne" in exp_or_ov:
                    results.append(_match_ne(doc, path_parts, exp_or_ov["$ne"]))
                if "$gt" in exp_or_ov:
                    results.append(_match_gt(doc, path_parts, exp_or_ov["$gt"]))
                if "$gte" in exp_or_ov:
                    results.append(_match_gte(doc, path_parts, exp_or_ov["$gte"]))
                if "$lt" in exp_or_ov:
                    results.append(_match_lt(doc, path_parts, exp_or_ov["$lt"]))
                if "$lte" in exp_or_ov:
                    results.append(_match_lte(doc, path_parts, exp_or_ov["$lte"]))
                if "$in" in exp_or_ov:
                    results.append(_match_in(doc, path_parts, exp_or_ov["$in"]))
                if "$nin" in exp_or_ov:
                    results.append(_match_nin(doc, path_parts, exp_or_ov["$nin"]))
                if "$not" in exp_or_ov:
                    results.append(not match_cond({path: exp_or_ov["$not"]}, doc))
                if "$regex" in exp_or_ov:
                    ov = {
                        "$regex": exp_or_ov["$regex"],
                        "$options": exp_or_ov.get("$options", ""),
                    }
                    results.append(_match_regex(doc, path_parts, ov))
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


def _match_ne(doc, path: List[str], ov) -> bool:
    return not _match_eq(doc, path, ov)


def _match_regex(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_regex(d, path, ov) for d in doc]):
            return True

        flags = re.NOFLAG
        if "i" in ov["$options"]:
            flags = flags | re.IGNORECASE
        if "m" in ov["$options"]:
            flags = flags | re.MULTILINE
        if "s" in ov["$options"]:
            flags = flags | re.DOTALL
        if "x" in ov["$options"]:
            flags = flags | re.VERBOSE

        matcher = re.compile(ov["$regex"], flags)

        if matcher.search(doc):
            return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_regex(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_regex(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_regex(d, path, ov) for d in doc])

    return False


def _match_in(doc, path: List[str], ov) -> bool:
    if not isinstance(ov, list):
        raise TypeError("$in operator value must be a list")

    if len(path) == 0:
        if isinstance(doc, list) and any([_match_in(d, path, ov) for d in doc]):
            return True

        return doc in ov

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_in(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_in(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_in(d, path, ov) for d in doc])

    if None in ov:
        return True

    return False


def _match_nin(doc, path: List[str], ov) -> bool:
    return not _match_in(doc, path, ov)


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
