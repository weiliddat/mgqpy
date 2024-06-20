"""mongo query as a python filter predicate"""

__version__ = "0.1.7"

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

from numbers import Number
import operator
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

    return ov is None


def _match_gt(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_gt(d, path, ov) for d in doc]):
            return True

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
