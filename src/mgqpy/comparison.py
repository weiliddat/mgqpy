"""Value equality, BSON ordering and pairwise native conversions (internal)."""

import datetime
from decimal import Decimal, InvalidOperation
from numbers import Number
import operator
import re
from uuid import UUID

from .path import MISSING


# The types representable without a BSON dependency. Numeric representations
# share a bracket; bool does not inherit int's bracket.
_KINDS = {type(None): 0, int: 1, float: 1, Decimal: 1, str: 2,
          dict: 3, list: 4, bytes: 5, bytearray: 5, UUID: 5, bool: 6,
          datetime.date: 7, datetime.datetime: 7, re.Pattern: 8}


def _kind(value):
    kind = _KINDS.get(type(value))
    if kind is not None:
        return kind
    for cls, kind in _KINDS.items():
        if isinstance(value, cls):
            return kind
    return 1 if isinstance(value, Number) else type(value)


def _is_nan(value):
    if isinstance(value, Decimal):
        return value.is_nan()
    return isinstance(value, float) and value != value


def equal(a, b) -> bool:
    if type(a) in (int, float) and type(b) in (int, float):
        return a == b or (a != a and b != b)
    if type(a) is str and type(b) is str:
        return a == b
    a, b = _coerce(a, b)
    kind = _kind(a)
    if kind != _kind(b):
        return False
    if kind == 1 and (_is_nan(a) or _is_nan(b)):
        return _is_nan(a) and _is_nan(b)
    if kind == 3:
        if len(a) != len(b):
            return False
        for (ak, av), (bk, bv) in zip(a.items(), b.items()):
            if ak != bk or not equal(av, bv):
                return False
        return True
    if kind == 4:
        if len(a) != len(b):
            return False
        for av, bv in zip(a, b):
            if not equal(av, bv):
                return False
        return True
    return a == b


def compare(a, b) -> int:
    """Recursive BSON ordering; query-level type brackets are applied outside."""
    if type(a) in (int, float) and type(b) in (int, float):
        if a != a:
            return 0 if b != b else -1
        if b != b:
            return 1
        return (a > b) - (a < b)
    a, b = _coerce(a, b)
    ak, bk = _kind(a), _kind(b)
    if ak != bk:
        return (ak > bk) - (ak < bk)
    if ak == 0:
        return 0
    if ak == 1 and (_is_nan(a) or _is_nan(b)):
        return 0 if _is_nan(a) and _is_nan(b) else -1 if _is_nan(a) else 1
    if ak == 3:
        for (an, av), (bn, bv) in zip(a.items(), b.items()):
            av, bv = _coerce(av, bv)
            at, bt = _kind(av), _kind(bv)
            if at != bt:
                return (at > bt) - (at < bt)
            if an != bn:
                if an > bn:
                    return 1
                return -1 if an < bn else 0
            result = compare(av, bv)
            if result:
                return result
        return (len(a) > len(b)) - (len(a) < len(b))
    if ak == 4:
        for av, bv in zip(a, b):
            result = compare(av, bv)
            if result:
                return result
        return (len(a) > len(b)) - (len(a) < len(b))
    if ak == 5:
        a = (len(a.bytes), 4, a.bytes) if isinstance(a, UUID) else (len(a), 0, bytes(a))
        b = (len(b.bytes), 4, b.bytes) if isinstance(b, UUID) else (len(b), 0, bytes(b))
    if ak == 8:
        a, b = _regex_key(a), _regex_key(b)
    if a > b:
        return 1
    return -1 if a < b else 0


def _range(value, operand, op, inclusive=False) -> bool:
    if value is MISSING:
        return inclusive and operand is None
    value, operand = _coerce(value, operand)
    kind = _kind(value)
    if kind != _kind(operand):
        return False
    # Mongo's direct ranges reject one-NaN comparisons. Container ordering
    # instead uses the total order in compare(), where NaN precedes -inf.
    if kind == 1 and (_is_nan(value) or _is_nan(operand)):
        return inclusive and _is_nan(value) and _is_nan(operand)
    if kind in (0, 3, 4, 5, 8):
        return op(compare(value, operand), 0)
    return op(value, operand)


# Exact built-in numbers bypass conversion and dynamic operator calls. Keeping
# these small entries direct matters when scanning long numeric arrays.
def _match_gt(value, operand) -> bool:
    if type(value) in (int, float) and type(operand) in (int, float):
        return value > operand
    return _range(value, operand, operator.gt)


def _match_gte(value, operand) -> bool:
    if type(value) in (int, float) and type(operand) in (int, float):
        return value >= operand or (value != value and operand != operand)
    return _range(value, operand, operator.ge, True)


def _match_lt(value, operand) -> bool:
    if type(value) in (int, float) and type(operand) in (int, float):
        return value < operand
    return _range(value, operand, operator.lt)


def _match_lte(value, operand) -> bool:
    if type(value) in (int, float) and type(operand) in (int, float):
        return value <= operand or (value != value and operand != operand)
    return _range(value, operand, operator.le, True)


def _regex_key(value):
    flags = "".join(letter for letter, flag in (("i", re.I), ("m", re.M),
                    ("s", re.S), ("u", re.U), ("x", re.X)) if value.flags & flag)
    return value.pattern, flags


def _coerce(a, b):
    """Convert only scalar pairs, lazily, including within containers."""
    if type(a) is type(b):
        return a, b
    match (a, b):
        case (datetime.datetime() as dt, str()):
            return dt, _try_date(b, datetime.datetime, dt.tzinfo)
        case (datetime.date() as d, str()):
            return d, _try_date(b, datetime.date)
        case (str(), datetime.datetime() as dt):
            return _try_date(a, datetime.datetime, dt.tzinfo), dt
        case (str(), datetime.date() as d):
            return _try_date(a, datetime.date), d
        case (Decimal(), _):
            return a, _try_decimal(b)
        case (_, Decimal()):
            return _try_decimal(a), b
        case (UUID(), str()):
            return a, _try_uuid(b)
        case (str(), UUID()):
            return _try_uuid(a), b
        case _:
            return a, b


def _try_date(value, target, tzinfo=None):
    try:
        if target is datetime.date:
            return datetime.date.fromisoformat(value)
        result = datetime.datetime.fromisoformat(value)
        if tzinfo is not None and result.tzinfo is None:
            return result.replace(tzinfo=tzinfo)
        return result
    except ValueError:
        return value


def _try_decimal(value):
    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            pass
    return value


def _try_uuid(value):
    try:
        return UUID(value)
    except ValueError:
        return value
