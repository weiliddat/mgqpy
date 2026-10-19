"""Numeric operand validation and canonical array-index spelling."""

from decimal import Decimal
import math
from numbers import Number


_EXCLUDED_NUMBERS = (bool, complex)


def is_array_index(key: str) -> bool:
    """Only canonical, nonnegative ASCII integers are array indices."""
    return key.isdecimal() and key.isascii() and (key == "0" or key[0] != "0")


def is_finite_number(value) -> bool:
    if not isinstance(value, Number) or isinstance(value, _EXCLUDED_NUMBERS):
        return False
    if isinstance(value, int):
        return True
    # The float-finite bound also prevents huge Decimal-to-integer truncations.
    try:
        return math.isfinite(value)
    except ValueError:
        # math.isfinite raises for Decimal sNaN; other conversion errors propagate.
        if isinstance(value, Decimal) and value.is_snan():
            return False
        raise
