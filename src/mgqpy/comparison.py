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
# Hot paths use annotated rank literals to avoid repeated global lookups.
_NULL = 0
_NUMBER = 1
_STRING = 2
_DOCUMENT = 3
_ARRAY = 4
_BINARY = 5
_BOOL = 6
_DATE = 7
_REGEX = 8

_KINDS = {type(None): _NULL, int: _NUMBER, float: _NUMBER, Decimal: _NUMBER, str: _STRING,
          dict: _DOCUMENT, list: _ARRAY, bytes: _BINARY, bytearray: _BINARY, UUID: _BINARY, bool: _BOOL,
          datetime.date: _DATE, datetime.datetime: _DATE, re.Pattern: _REGEX}
_NUMERIC_TYPES = (int, float)
# Pairs of distinct exact types from this set never convert, so they can be
# equal only within one bracket (int/float, bytes/bytearray).
_UNCONVERTED = frozenset((type(None), bool, int, float, str, bytes, bytearray, dict, list, re.Pattern))
# Non-NaN values of these exact types are equal exactly when Python equality
# says so, which permits C-level equality, membership and hashing.
_PLAIN = frozenset((type(None), int, float, str))
# Bound once: CPython 3.11 compiles method calls on imported names as slower attribute loads.
_all_plain = _PLAIN.issuperset
# equal() compares document keys with their own !=; only exact str keys let
# Python dict equality decide instead.
_all_str = frozenset((str,)).issuperset
# Above this length, certifying every member costs more than equal() needs to
# reject at an early mismatch.
_PLAIN_CONTAINER_LIMIT = 16


def all_plain_operands(values) -> bool:
    """Whether Python equality decides equal() against each of these operands."""
    # operator.eq, unlike container equality, finds NaN members.
    return _all_plain(map(type, values)) and all(map(operator.eq, values, values))


def _kind(value):
    # Exact types take precedence: bool must not enter int's subclass bracket.
    kind = _KINDS.get(type(value))
    if kind is not None:
        return kind
    for cls, kind in _KINDS.items():
        if isinstance(value, cls):
            return kind
    return 1 if isinstance(value, Number) else None  # _NUMBER


def _is_nan(value):
    if isinstance(value, Decimal):
        return value.is_nan()
    return isinstance(value, float) and value != value


def equal(a, b) -> bool:
    if a is MISSING:
        return b is None
    at, bt = type(a), type(b)
    if at is not bt:
        if at in _UNCONVERTED and bt in _UNCONVERTED:
            return _KINDS[at] == _KINDS[bt] and a == b
        a, b = _coerce(a, b)
        at, bt = type(a), type(b)
        # Aligned native scalars use the general scalar equality below.
        if at is bt and at is not Decimal:
            return a == b
    if at is bt:
        # Exact ints/strings use the general same-kind scalar equality.
        if at is int or at is str:
            return a == b
        # Exact floats use the general numeric equality, including NaNs.
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
    if kind == 1 and (_is_nan(a) or _is_nan(b)):  # _NUMBER
        return _is_nan(a) and _is_nan(b)
    if kind == 3:  # _DOCUMENT
        if len(a) != len(b):
            return False
        for (ak, av), (bk, bv) in zip(a.items(), b.items()):
            if ak != bk or not equal(av, bv):
                return False
        return True
    if kind == 4:  # _ARRAY
        if len(a) != len(b):
            return False
        for av, bv in zip(a, b):
            if not equal(av, bv):
                return False
        return True
    return a == b


def prepare_equal(operand):
    """Return a match(value, operand) equivalent to equal() for this operand."""
    if type(operand) is list:
        members = operand
    elif type(operand) is dict:
        members = operand.values()
    else:
        return equal
    # Small flat plain containers compare in C once the value is certified the same way.
    if len(members) > _PLAIN_CONTAINER_LIMIT or not all_plain_operands(members):
        return equal
    if members is operand:
        return _equal_plain_list
    return _equal_plain_dict if _all_str(map(type, operand)) else equal


def _equal_plain_list(value, operand):
    if type(value) is list:
        if len(value) != len(operand):
            return False
        if _all_plain(map(type, value)):
            return value == operand
    return equal(value, operand)


def _equal_plain_dict(value, operand):
    if type(value) is dict:
        if len(value) != len(operand):
            return False
        if _all_str(map(type, value)) and _all_plain(map(type, value.values())):
            # Python dict equality ignores key order.
            return value == operand and all(map(operator.eq, value, operand))
    return equal(value, operand)


def compare(a, b) -> int:
    """Recursive BSON ordering; query-level type brackets are applied outside."""
    # Exact numbers use _compare's general numeric order without preparation.
    if type(a) in _NUMERIC_TYPES and type(b) in _NUMERIC_TYPES:
        if a != a:
            return 0 if b != b else -1
        if b != b:
            return 1
        return (a > b) - (a < b)
    # Same-type pairs need only one classification, equivalent to pair preparation.
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
    if kind == 3:  # _DOCUMENT
        for (an, av), (bn, bv) in zip(a.items(), b.items()):
            at, bt = type(av), type(bv)
            if at is not bt:
                av, bv = _coerce(av, bv)
                at, bt = type(av), type(bv)
            # Exact int/string fields use the general kind check and _compare order.
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
    if kind == 0:  # _NULL
        return 0
    if kind == 1:  # _NUMBER
        # Exact numbers use the general NaN-aware numeric order below.
        if type(a) in _NUMERIC_TYPES and type(b) in _NUMERIC_TYPES:
            if a != a:
                return 0 if b != b else -1
            if b != b:
                return 1
            return (a > b) - (a < b)
        if _is_nan(a) or _is_nan(b):
            return 0 if _is_nan(a) and _is_nan(b) else -1 if _is_nan(a) else 1
    if kind == 4:  # _ARRAY
        for av, bv in zip(a, b):
            result = compare(av, bv)
            if result:
                return result
        return (len(a) > len(b)) - (len(a) < len(b))
    if kind == 5:  # _BINARY
        # Bytes use the general (length, subtype=0, payload) binary order.
        if type(a) is bytes and type(b) is bytes:
            if len(a) != len(b):
                return (len(a) > len(b)) - (len(a) < len(b))
            return (a > b) - (a < b)
        a = (len(a.bytes), 4, a.bytes) if isinstance(a, UUID) else (len(a), 0, bytes(a))
        b = (len(b.bytes), 4, b.bytes) if isinstance(b, UUID) else (len(b), 0, bytes(b))
    if kind == 8:  # _REGEX
        a, b = _regex_key(a), _regex_key(b)
    if a > b:
        return 1
    return -1 if a < b else 0


def _range(value, operand, op, inclusive=False) -> bool:
    if value is MISSING:
        return inclusive and operand is None
    # Same-type pairs need only one classification, equivalent to pair preparation.
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
    if kind == 1 and (_is_nan(value) or _is_nan(operand)):  # _NUMBER
        return inclusive and _is_nan(value) and _is_nan(operand)
    if kind in (0, 3, 4, 5, 8):  # _NULL, _DOCUMENT, _ARRAY, _BINARY, _REGEX
        return op(_compare(value, operand, kind), 0)
    return op(value, operand)


# Exact built-in numbers and documents bypass redundant preparation and dynamic
# operator calls. These small entries matter when scanning long arrays.
def _match_gt(value, operand) -> bool:
    # Exact numbers/documents use _range's general bracketed comparison.
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value > operand
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) > 0  # _DOCUMENT
    return _range(value, operand, operator.gt)


def _match_gte(value, operand) -> bool:
    # Exact numbers/documents use _range's general bracketed comparison.
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value >= operand or (value != value and operand != operand)
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) >= 0  # _DOCUMENT
    return _range(value, operand, operator.ge, True)


def _match_lt(value, operand) -> bool:
    # Exact numbers/documents use _range's general bracketed comparison.
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value < operand
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) < 0  # _DOCUMENT
    return _range(value, operand, operator.lt)


def _match_lte(value, operand) -> bool:
    # Exact numbers/documents use _range's general bracketed comparison.
    if type(value) in _NUMERIC_TYPES and type(operand) in _NUMERIC_TYPES:
        return value <= operand or (value != value and operand != operand)
    if type(value) is dict and type(operand) is dict:
        return _compare(value, operand, 3) <= 0  # _DOCUMENT
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
