"""mongo query as a predicate function"""

__version__ = "0.6.0"

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

from typing import List

from .operators.and_or_nor import _match_and, _match_or, _match_nor, _validate_query_ops
from .operators.all import _match_all, _validate_all
from .operators.elem_match import _match_elem_match
from .operators.eq_ne_not import _match_eq, _match_ne, _match_not
from .operators.gt import _match_gt
from .operators.gte import _match_gte
from .operators.in_nin import _match_in, _match_nin, _validate_in_nin
from .operators.lt import _match_lt
from .operators.lte import _match_lte
from .operators.mod import _match_mod, _validate_mod
from .operators.regex import _match_regex
from .operators.size import _match_size, _validate_size

cond_ops = {
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
    "$mod",
    "$all",
    "$elemMatch",
    "$size",
}

query_ops = {
    "$and",
    "$or",
    "$nor",
}


class Query:
    def __init__(self, query):
        self._query = query
        pass

    def match(self, doc) -> bool:
        return _match_cond(self._query, doc)

    def validate(self):
        _validate(self._query)
        return self


def _match_cond(query, doc):
    results: List[bool] = []

    for path in query:
        if isinstance(path, str) and path in query_ops:
            if path == "$and":
                results.append(_match_and(doc, path, query["$and"]))
            if path == "$or":
                results.append(_match_or(doc, path, query["$or"]))
            if path == "$nor":
                results.append(_match_nor(doc, path, query["$nor"]))
        else:
            exp_or_ov = query[path]
            is_all_exp = _check_all_exp(exp_or_ov)
            path_parts = path.split(".")

            if is_all_exp:
                exp = exp_or_ov
                if "$eq" in exp:
                    results.append(_match_eq(doc, path_parts, exp["$eq"]))
                if "$ne" in exp:
                    results.append(_match_ne(doc, path_parts, exp["$ne"]))
                if "$gt" in exp:
                    results.append(_match_gt(doc, path_parts, exp["$gt"]))
                if "$gte" in exp:
                    results.append(_match_gte(doc, path_parts, exp["$gte"]))
                if "$lt" in exp:
                    results.append(_match_lt(doc, path_parts, exp["$lt"]))
                if "$lte" in exp:
                    results.append(_match_lte(doc, path_parts, exp["$lte"]))
                if "$in" in exp:
                    results.append(_match_in(doc, path_parts, exp["$in"]))
                if "$nin" in exp:
                    results.append(_match_nin(doc, path_parts, exp["$nin"]))
                if "$not" in exp:
                    results.append(_match_not(doc, path, exp["$not"]))
                if "$regex" in exp:
                    ov = {
                        "$regex": exp["$regex"],
                        "$options": exp.get("$options", ""),
                    }
                    results.append(_match_regex(doc, path_parts, ov))
                if "$mod" in exp:
                    results.append(_match_mod(doc, path_parts, exp["$mod"]))
                if "$all" in exp:
                    results.append(_match_all(doc, path_parts, exp["$all"]))
                if "$elemMatch" in exp:
                    results.append(
                        _match_elem_match(doc, path_parts, exp["$elemMatch"])
                    )
                if "$size" in exp:
                    results.append(_match_size(doc, path_parts, exp["$size"]))
            else:
                ov = exp_or_ov
                results.append(_match_eq(doc, path_parts, ov))

    return all(results)


def _validate(query) -> bool:
    if not isinstance(query, dict):
        raise TypeError("query must be a dict")

    for path in query:
        if isinstance(path, str) and path in query_ops:
            if path == "$and":
                if not _validate_query_ops(query["$and"]):
                    raise TypeError("$and operator value must be a list")
            if path == "$or":
                if not _validate_query_ops(query["$or"]):
                    raise TypeError("$or operator value must be a list")
            if path == "$nor":
                if not _validate_query_ops(query["$nor"]):
                    raise TypeError("$nor operator value must be a list")
            for cond in query[path]:
                _validate(cond)
        else:
            exp_or_ov = query[path]
            is_all_exp = _check_all_exp(exp_or_ov)
            if is_all_exp:
                exp = exp_or_ov
                if "$in" in exp and not _validate_in_nin(exp["$in"]):
                    raise TypeError("$in operator value must be a list")
                if "$nin" in exp and not _validate_in_nin(exp["$nin"]):
                    raise TypeError("$nin operator value must be a list")
                if "$all" in exp and not _validate_all(exp["$all"]):
                    raise TypeError("$all operator value must be a list")
                if "$mod" in exp and not _validate_mod(exp["$mod"]):
                    raise TypeError("$mod operator value must be a list of 2 numbers")
                if "$size" in exp and not _validate_size(exp["$size"]):
                    raise TypeError("$size operator value must be a number")

    return True


def _check_all_exp(exp_or_ov):
    return (
        exp_or_ov
        and isinstance(exp_or_ov, dict)
        and all(key in cond_ops for key in exp_or_ov.keys())
    )
