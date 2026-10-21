"""$type: a value's BSON type, using the brackets of equality and ordering."""

import datetime
import re
from decimal import Decimal
from uuid import UUID

from mgqpy.utils import is_finite_number

_ALIASES = {
    "double": 1, "string": 2, "object": 3, "array": 4, "binData": 5, "undefined": 6,
    "objectId": 7, "bool": 8, "date": 9, "null": 10, "regex": 11, "dbPointer": 12,
    "javascript": 13, "symbol": 14, "javascriptWithScope": 15, "int": 16,
    "timestamp": 17, "long": 18, "decimal": 19, "minKey": -1, "maxKey": 127,
}
_CODES = frozenset(_ALIASES.values())
_NUMBER = frozenset((1, 16, 18, 19))

# Insertion order is the subclass fallback order: bool before int.
_TYPE_CODES = {
    type(None): 10, bool: 8, int: 16, float: 1, Decimal: 19, str: 2, dict: 3, list: 4,
    bytes: 5, bytearray: 5, UUID: 5, datetime.date: 9, datetime.datetime: 9, re.Pattern: 11,
}


def _type_code(value):
    code = _TYPE_CODES.get(type(value))
    if code is None:
        code = next((c for cls, c in _TYPE_CODES.items() if isinstance(value, cls)), None)
    # Python ints encode as int32, then int64; larger ones have no BSON type.
    if code == 16 and not -2**31 <= value < 2**31:
        return 18 if -2**63 <= value < 2**63 else None
    return code


def _match_type(value, codes) -> bool:
    return _type_code(value) in codes


def _compile_type(operand) -> frozenset:
    items = operand if isinstance(operand, list) else [operand]
    if not items:
        raise TypeError("$type requires at least one type")
    codes = set()
    for item in items:
        if isinstance(item, str):
            if item == "number":
                codes |= _NUMBER
            elif item in _ALIASES:
                codes.add(_ALIASES[item])
            else:
                raise TypeError(f"unknown $type alias: {item!r}")
        elif is_finite_number(item) and item == int(item) and int(item) in _CODES:
            codes.add(int(item))
        else:
            raise TypeError(f"invalid $type code: {item!r}")
    return frozenset(codes)
