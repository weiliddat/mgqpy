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
_NUMERIC_TYPES = (int, float)


def _kind(value):
    kind = _KINDS.get(type(value))
    if kind is not None:
        return kind
    for cls, kind in _KINDS.items():
        if isinstance(value, cls):
            return kind
    return 1 if isinstance(value, Number) else None


def _is_nan(value):
    if isinstance(value, Decimal):
        return value.is_nan()
    return isinstance(value, float) and value != value


def _python_equality_safe(value, depth=8):
    """Certify exact built-ins only; bounded depth also rejects cycles."""
    kind = type(value)
    if kind is int or kind is str or kind is bool or kind is bytes or value is None:
        return True
    if kind is float:
        return value == value
    if depth:
        if kind is dict:
            return all(type(k) is str and _python_equality_safe(v, depth - 1)
                       for k, v in value.items())
        if kind is list:
            return all(_python_equality_safe(v, depth - 1) for v in value)
    return False


def _expand_equal(values, operand, expand):
    # Keep first-element hits cheap. A Python hit is never an acceptance oracle.
    for index, value in enumerate(values):
        if index == 1 and type(values) is list and _python_equality_safe(values):
            if operand not in values:
                return equal(values, operand)
        if equal(value, operand):
            return True
    return equal(values, operand)


def equal(a, b) -> bool:
    if a is MISSING:
        return b is None
    at, bt = type(a), type(b)
    if at is not bt:
        if at in _NUMERIC_TYPES and bt in _NUMERIC_TYPES:
            return a == b
        a, b = _coerce(a, b)
        at, bt = type(a), type(b)
        # Successful date/UUID conversions align native scalar types. Decimal
        # still needs the shared NaN handling below.
        if at is bt and at is not Decimal:
            return a == b
    if at is bt:
        if at is int or at is str:
            return a == b
        if at is float:
            return a == b or (a != a and b != b)
        kind = _KINDS.get(at)
        if kind is None:
            kind = _kind(a)
    else:
        kind, other = _kind(a), _kind(b)
        if kind is None or other is None:
            return a == b
        if kind != other:
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
    if type(a) in _NUMERIC_TYPES and type(b) in _NUMERIC_TYPES:
        if a != a:
            return 0 if b != b else -1
        if b != b:
            return 1
        return (a > b) - (a < b)
    if type(a) is type(b):
        kind = _kind(a)
    else:
        a, b = _coerce(a, b)
        ak, bk = _kind(a), _kind(b)
        if ak is not None and bk is not None and ak != bk:
            return (ak > bk) - (ak < bk)
        kind = ak if bk is not None else None
    return _compare(a, b, kind)


def _compare(a, b, kind):
    """Order an already converted pair in one bracket (None means Python)."""
    if kind == 3:
        for (an, av), (bn, bv) in zip(a.items(), b.items()):
            at, bt = type(av), type(bv)
            if at is not bt:
                av, bv = _coerce(av, bv)
                at, bt = type(av), type(bv)
            simple = at is bt and (at is int or at is str)
            if not simple:
                ak, bk = _kind(av), _kind(bv)
                if ak is not None and bk is not None and ak != bk:
                    return (ak > bk) - (ak < bk)
            if an != bn:
                if an > bn:
                    return 1
                return -1 if an < bn else 0
            if simple:
                if av > bv:
                    return 1
                if av < bv:
                    return -1
            else:
                result = _compare(av, bv, ak if bk is not None else None)
                if result:
                    return result
        return (len(a) > len(b)) - (len(a) < len(b))
    if kind is None:
        if a > b:
            return 1
        return -1 if a < b else 0
    if kind == 0:
        return 0
    if kind == 1:
        if type(a) in _NUMERIC_TYPES and type(b) in _NUMERIC_TYPES:
            if a != a:
                return 0 if b != b else -1
            if b != b:
                return 1
            return (a > b) - (a < b)
        if _is_nan(a) or _is_nan(b):
            return 0 if _is_nan(a) and _is_nan(b) else -1 if _is_nan(a) else 1
    if kind == 4:
        for av, bv in zip(a, b):
            result = compare(av, bv)
            if result:
                return result
        return (len(a) > len(b)) - (len(a) < len(b))
    if kind == 5:
        if type(a) is bytes and type(b) is bytes:
            if len(a) != len(b):
                return (len(a) > len(b)) - (len(a) < len(b))
            return (a > b) - (a < b)
        a = (len(a.bytes), 4, a.bytes) if isinstance(a, UUID) else (len(a), 0, bytes(a))
        b = (len(b.bytes), 4, b.bytes) if isinstance(b, UUID) else (len(b), 0, bytes(b))
    if kind == 8:
        a, b = _regex_key(a), _regex_key(b)
    if a > b:
        return 1
    return -1 if a < b else 0


def _range(value, operand, op, inclusive=False) -> bool:
    if value is MISSING:
        return inclusive and operand is None
    if type(value) is type(operand):
        kind = other = _kind(value)
    else:
        value, operand = _coerce(value, operand)
        kind, other = _kind(value), _kind(operand)
    if kind is None or other is None:
        return op(value, operand)
    if kind != other:
        return False
    # Mongo's direct ranges reject one-NaN comparisons. Container ordering
    # instead uses the total order in compare(), where NaN precedes -inf.
    if kind == 1 and (_is_nan(value) or _is_nan(operand)):
        return inclusive and _is_nan(value) and _is_nan(operand)
    if kind in (0, 3, 4, 5, 8):
        return op(_compare(value, operand, kind), 0)
    return op(value, operand)


# Exact built-in numbers and documents bypass redundant preparation and dynamic
# operator calls. These small entries matter when scanning long arrays.
def _match_gt(value, operand) -> bool:
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value > operand
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) > 0
    return _range(value, operand, operator.gt)


def _match_gte(value, operand) -> bool:
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value >= operand or (value != value and operand != operand)
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) >= 0
    return _range(value, operand, operator.ge, True)


def _match_lt(value, operand) -> bool:
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value < operand
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) < 0
    return _range(value, operand, operator.lt)


def _match_lte(value, operand) -> bool:
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value <= operand or (value != value and operand != operand)
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) <= 0
    return _range(value, operand, operator.le, True)


def _regex_key(value):
    flags = "".join(letter for letter, flag in (("i", re.I), ("m", re.M),
                    ("s", re.S), ("u", re.U), ("x", re.X)) if value.flags & flag)
    return value.pattern, flags


def _coerce(a, b):
    """Convert only scalar pairs, lazily, including within containers."""
    if isinstance(b, str):
        if isinstance(a, datetime.datetime):
            return a, _try_date(b, datetime.datetime, a.tzinfo)
        if isinstance(a, datetime.date):
            return a, _try_date(b, datetime.date)
        if isinstance(a, UUID):
            return a, _try_uuid(b)
    if isinstance(a, str):
        if isinstance(b, datetime.datetime):
            return _try_date(a, datetime.datetime, b.tzinfo), b
        if isinstance(b, datetime.date):
            return _try_date(a, datetime.date), b
        if isinstance(b, UUID):
            return _try_uuid(a), b
    if isinstance(a, Decimal):
        return a, _try_decimal(b)
    if isinstance(b, Decimal):
        return _try_decimal(a), b
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
