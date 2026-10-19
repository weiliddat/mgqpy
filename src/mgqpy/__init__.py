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
from numbers import Number
import re
from typing import Any

from .comparison import equal as _equal, _match_gt, _match_gte, _match_lt, _match_lte
from .operators.all import _SIMPLE, compile_all
from .operators.and_or_nor import conjunction, disjunction, negate
from .operators.elem_match import _match_elem_match, _match_elem_match_value, _match_elem_match_pair
from .operators.eq_ne_not import _match_eq
from .operators.exists import _match_exists
from .operators.in_nin import _match_in, prepare_in
from .operators.mod import _match_mod, _validate_mod
from .operators.regex import _Regex, _match_regex, _compile_regex
from .operators.size import _match_size, _validate_size
from .path import bind_path, compile_path

__all__ = ("Query", "InvalidQuery")

query_ops = {
    "$and",
    "$or",
    "$nor",
}


class InvalidQuery(ValueError):
    """The query is malformed or uses an unsupported operator or regex."""


class Query:
    def __init__(self, query: dict[str, Any]):
        try:
            self._query = _copy_query(query)
            self._match = _compile_query(self._query)
        except InvalidQuery:
            raise
        except (TypeError, ValueError, ArithmeticError, RecursionError) as error:
            raise InvalidQuery(str(error)) from error

    def __reduce__(self):
        # Local compiled closures are rebuilt from the isolated source snapshot.
        return type(self), (self._query,)

    def test(self, doc: dict[str, Any]) -> bool:
        if not isinstance(doc, dict):
            raise TypeError("document must be a dict")
        return bool(self._match(doc))


def _compile_query(query, location="query"):
    if not isinstance(query, dict):
        raise InvalidQuery(f"{location}: query must be a dict")
    predicates = []
    for path, value in query.items():
        here = f"{location}.{path}"
        try:
            if path.startswith("$") and path not in query_ops:
                raise TypeError(f"unknown top-level operator: {path}")
            if path in query_ops:
                if not isinstance(value, list) or not value:
                    raise TypeError(f"{path} operator value must be a nonempty list")
                children = tuple(_compile_query(child, f"{here}[{i}]") for i, child in enumerate(value))
                predicate = conjunction(children) if path == "$and" else disjunction(children)
                predicates.append(negate(predicate) if path == "$nor" else predicate)
            else:
                value = _prepare_expression(value, here)
                predicates.append(_compile_expression(compile_path(path), value))
        except InvalidQuery:
            raise
        except (TypeError, ValueError, ArithmeticError, RecursionError) as error:
            raise InvalidQuery(f"{here}: {error}") from error
    return conjunction(tuple(predicates))


def _field(parts, match, operand, expand_leaf=True):
    # None binds a raw $elemMatch element, without path lookup or expansion.
    if parts is None:
        def predicate(value):
            return match(value, operand)
        return predicate
    return bind_path(parts, match, operand, expand_leaf)


# Preserve the established operator evaluation order, independent of key order.
_value_ops = {
    "$eq": _equal, "$ne": _equal,
    "$gt": _match_gt, "$gte": _match_gte, "$lt": _match_lt, "$lte": _match_lte,
    "$in": _match_in, "$nin": _match_in, "$not": None,
    "$regex": _match_regex, "$mod": _match_mod, "$all": None,
    "$elemMatch": None, "$size": _match_size, "$exists": _match_exists,
}


def _compile_expression(parts, value):
    if not _is_expression(value):
        return _field(parts, _match_eq if isinstance(value, _Regex) else _equal, value)
    predicates = []
    for op, match in _value_ops.items():
        if op not in value:
            continue
        operand = value[op]
        if op == "$not":
            predicate = negate(_compile_expression(parts, operand))
        elif op == "$all":
            if not operand:
                predicate = disjunction(())
            elif parts is None:
                # Every requirement tests the same raw $elemMatch element.
                predicate = conjunction(tuple(_compile_expression(parts, child) for child in operand))
            elif len(operand) == 1 and type(operand[0]) not in _SIMPLE:
                # Numbers/strings keep their faster chunked membership path.
                predicate = _compile_expression(parts, operand[0])
            elif _is_expression(operand[0]):
                children = tuple(child["$elemMatch"] for child in operand)
                match = children[0][0]
                if all(m is match for m, _ in children):
                    predicate = compile_all(parts, tuple(child for _, child in children), match)
                else:
                    predicate = compile_all(parts, children, _match_elem_match_pair)
            else:
                predicate = compile_all(parts, tuple(operand), _match_eq)
        elif op == "$elemMatch":
            match, child = operand
            predicate = _field(parts, match, child, False)
        else:
            predicate = _field(parts, match, operand, op not in {"$size", "$exists"})
            if op in {"$ne", "$nin"}:
                predicate = negate(predicate)
            if op == "$exists" and (operand is None or (isinstance(operand, Number) and not operand)):
                predicate = negate(predicate)
        predicates.append(predicate)
    return conjunction(tuple(predicates))


def _prepare_expression(value, location):
    if isinstance(value, re.Pattern):
        return _compile_regex(value)
    # As in MongoDB, the first key distinguishes an expression from a literal.
    if not _is_expression(value):
        return value

    # A caller can reuse a dict/list as both an expression and a literal operand.
    # Normalize expressions without changing that literal, even in our snapshot.
    value = value.copy()
    for op in value:
        if op not in _value_ops and op != "$options":
            raise TypeError(f"unknown operator: {op}")
        if op in {"$ne", "$gt", "$gte", "$lt", "$lte"} and isinstance(value[op], re.Pattern):
            raise TypeError(f"{op} does not accept a regex operand")
    if "$options" in value and "$regex" not in value:
        raise TypeError("$options requires $regex")
    if "$regex" in value:
        value["$regex"] = _compile_regex(value["$regex"], value.pop("$options", ""))
    if "$not" in value:
        child = value["$not"]
        if not isinstance(child, re.Pattern) and not _is_expression(child):
            raise TypeError("$not requires a regex or a nonempty operator expression")
        value["$not"] = _prepare_expression(child, f"{location}.$not")
    if "$elemMatch" in value:
        child = value["$elemMatch"]
        if not isinstance(child, dict):
            raise TypeError("$elemMatch operator value must be a dict")
        here = f"{location}.$elemMatch"
        if _is_expression(child) and next(iter(child)) not in query_ops:
            try:
                predicate = _compile_expression(None, _prepare_expression(child, here))
            except InvalidQuery:
                raise
            except (TypeError, ValueError, ArithmeticError, RecursionError) as error:
                raise InvalidQuery(f"{here}: {error}") from error
            value["$elemMatch"] = (_match_elem_match_value, predicate)
        else:
            value["$elemMatch"] = (_match_elem_match, _compile_query(child, here))
    for op in ("$in", "$nin", "$all"):
        if op not in value:
            continue
        operands = value[op]
        if not isinstance(operands, list):
            raise TypeError(f"{op} operator value must be a list")
        operands = value[op] = operands.copy()
        for i, operand in enumerate(operands):
            if _is_expression(operand):
                if op != "$all" or set(operand) != {"$elemMatch"}:
                    raise TypeError(f"{op} does not accept operator expressions here")
                operands[i] = _prepare_expression(operand, f"{location}.{op}[{i}]")
            elif isinstance(operand, re.Pattern):
                operands[i] = _compile_regex(operand)
        if op != "$all":
            value[op] = prepare_in(operands)
        if op == "$all":
            has_elem_match = any(_is_expression(o) for o in operands)
            if has_elem_match and not all(_is_expression(o) and set(o) == {"$elemMatch"} for o in operands):
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


def _is_expression(value):
    return isinstance(value, dict) and bool(value) and next(iter(value)).startswith("$")
