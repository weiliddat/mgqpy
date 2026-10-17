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

from copy import deepcopy
import math
import re

from .operators.and_or_nor import _match_and, _match_or, _match_nor, _validate_query_ops
from .operators.all import _match_all, _validate_all, _is_all_elem_match
from .operators.elem_match import _match_elem_match
from .operators.eq_ne_not import _match_eq, _match_ne, _match_not
from .operators.exists import _match_exists
from .operators.gt import _match_gt
from .operators.gte import _match_gte
from .operators.in_nin import _match_in, _match_nin
from .operators.lt import _match_lt
from .operators.lte import _match_lte
from .operators.mod import _match_mod, _validate_mod
from .operators.regex import _match_regex, _compile_regex
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
    "$exists",
}

query_ops = {
    "$and",
    "$or",
    "$nor",
}


class InvalidQuery(ValueError):
    """The query is malformed or uses an unsupported operator or regex."""


class Query:
    def __init__(self, query):
        try:
            self._query = _validate(_copy_query(query))
        except (TypeError, ValueError, ArithmeticError, RecursionError) as error:
            raise InvalidQuery(str(error)) from error

    def test(self, doc) -> bool:
        if not isinstance(doc, dict):
            raise TypeError("document must be a dict")
        return _match_cond(self._query, doc)


def _match_cond(query, doc):
    for path in query:
        if path in query_ops:
            if path == "$and" and not _match_and(doc, path, query["$and"]):
                return False
            if path == "$or" and not _match_or(doc, path, query["$or"]):
                return False
            if path == "$nor" and not _match_nor(doc, path, query["$nor"]):
                return False
        else:
            exp_or_ov = query[path]
            is_all_exp = _check_all_exp(exp_or_ov)
            path_parts = path.split(".")

            if is_all_exp:
                exp = exp_or_ov
                if "$eq" in exp and not _match_eq(doc, path_parts, exp["$eq"]):
                    return False
                if "$ne" in exp and not _match_ne(doc, path_parts, exp["$ne"]):
                    return False
                if "$gt" in exp and not _match_gt(doc, path_parts, exp["$gt"]):
                    return False
                if "$gte" in exp and not _match_gte(doc, path_parts, exp["$gte"]):
                    return False
                if "$lt" in exp and not _match_lt(doc, path_parts, exp["$lt"]):
                    return False
                if "$lte" in exp and not _match_lte(doc, path_parts, exp["$lte"]):
                    return False
                if "$in" in exp and not _match_in(doc, path_parts, exp["$in"]):
                    return False
                if "$nin" in exp and not _match_nin(doc, path_parts, exp["$nin"]):
                    return False
                if "$not" in exp and not _match_not(doc, path, exp["$not"]):
                    return False
                if "$regex" in exp and not _match_regex(doc, path_parts, exp["$regex"]):
                    return False
                if "$mod" in exp and not _match_mod(doc, path_parts, exp["$mod"]):
                    return False
                if "$all" in exp and not _match_all(doc, path_parts, exp["$all"]):
                    return False
                if "$elemMatch" in exp and not _match_elem_match(doc, path_parts, exp["$elemMatch"]):
                    return False
                if "$size" in exp and not _match_size(doc, path_parts, exp["$size"]):
                    return False
                if "$exists" in exp and not _match_exists(doc, path_parts, exp["$exists"]):
                    return False
            else:
                ov = exp_or_ov
                if not _match_eq(doc, path_parts, ov):
                    return False

    return True


def _validate(query):
    if not isinstance(query, dict):
        raise TypeError("query must be a dict")

    query = query.copy()
    for path, value in query.items():
        if path.startswith("$") and path not in query_ops:
            raise TypeError(f"unknown top-level operator: {path}")
        if path in query_ops:
            if not _validate_query_ops(value) or not value:
                raise TypeError(f"{path} operator value must be a nonempty list")
            query[path] = [_validate(child) for child in value]
        else:
            query[path] = _validate_expression(value)
    return query


def _validate_expression(value):
    if isinstance(value, re.Pattern):
        return _compile_regex(value)
    # As in MongoDB, the first key distinguishes an expression from a literal.
    if not isinstance(value, dict) or not value or not next(iter(value)).startswith("$"):
        return value

    # A caller can reuse a dict/list as both an expression and a literal operand.
    # Normalize expressions without changing that literal, even in our snapshot.
    value = value.copy()
    for op in value:
        if op not in cond_ops:
            raise TypeError(f"unknown operator: {op}")
        if op in {"$ne", "$gt", "$gte", "$lt", "$lte"} and isinstance(value[op], re.Pattern):
            raise TypeError(f"{op} does not accept a regex operand")
    if "$options" in value and "$regex" not in value:
        raise TypeError("$options requires $regex")
    if "$regex" in value:
        value["$regex"] = _compile_regex(value["$regex"], value.pop("$options", ""))
    if "$not" in value:
        child = value["$not"]
        if not isinstance(child, re.Pattern) and not (
            isinstance(child, dict) and child and next(iter(child)).startswith("$")
        ):
            raise TypeError("$not requires a regex or a nonempty operator expression")
        value["$not"] = _validate_expression(child)
    if "$elemMatch" in value:
        child = value["$elemMatch"]
        if not isinstance(child, dict):
            raise TypeError("$elemMatch operator value must be a dict")
        if any(key.startswith("$") and key not in query_ops for key in child):
            raise TypeError("$elemMatch with operators on values is not supported")
        value["$elemMatch"] = _validate(child)
    for op in ("$in", "$nin", "$all"):
        if op not in value:
            continue
        operands = value[op]
        if not isinstance(operands, list):
            raise TypeError(f"{op} operator value must be a list")
        operands = value[op] = operands.copy()
        for i, operand in enumerate(operands):
            if _check_all_exp(operand):
                if op != "$all" or set(operand) != {"$elemMatch"}:
                    raise TypeError(f"{op} does not accept operator expressions here")
                operands[i] = _validate_expression(operand)
            elif isinstance(operand, re.Pattern) and op != "$all":
                operands[i] = _compile_regex(operand)
        if op == "$all":
            has_elem_match = any(isinstance(o, dict) and "$elemMatch" in o for o in operands)
            if not _validate_all(operands) or (has_elem_match and not _is_all_elem_match(operands)):
                raise TypeError("$all cannot mix $elemMatch with literal values")
    if "$mod" in value:
        if not _validate_mod(value["$mod"]):
            raise TypeError("$mod requires two finite int64-convertible numbers and a nonzero truncated divisor")
        divisor, remainder = map(math.trunc, value["$mod"])
        value["$mod"] = (abs(divisor), remainder)
    if "$size" in value:
        if not _validate_size(value["$size"]):
            raise TypeError("$size requires a nonnegative int32")
        value["$size"] = int(value["$size"])
    return value


def _copy_query(value):
    """Copy query containers while checking keys, sharing only immutable scalars."""
    if type(value) in (str, int, float, bool, bytes, complex, type(None)):
        return value
    if type(value) is dict:
        result = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("field keys must be strings")
            result[key] = _copy_query(child)
        return result
    if type(value) is list:
        return [_copy_query(child) for child in value]
    if type(value) is tuple:
        return tuple(_copy_query(child) for child in value)
    # Preserve deepcopy behavior for native types and container subclasses.
    _validate_keys(value)
    return deepcopy(value)


def _validate_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("field keys must be strings")
            _validate_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_keys(child)


def _check_all_exp(exp_or_ov):
    return (
        exp_or_ov
        and isinstance(exp_or_ov, dict)
        and next(iter(exp_or_ov)).startswith("$")
    )
