"""Numeric operand validation and canonical array-index spelling."""

from functools import lru_cache
import math
from numbers import Number


@lru_cache(maxsize=128)
def is_array_index(key: str) -> bool:
    """Only canonical, nonnegative ASCII integers are array indices."""
    return key == "0" or (key.isascii() and key.isdecimal() and key[0] != "0")


def is_finite_number(value) -> bool:
    return (
        isinstance(value, Number)
        and not isinstance(value, (bool, complex))
        and (isinstance(value, int) or math.isfinite(value))
    )
