import sys

from ..comparison import _PLAIN, _UNCONVERTED, all_plain_operands
from ..path import MISSING
from .eq_ne_not import _match_eq


_MODULUS = sys.hash_info.modulus
_NUMBERS = (int, float)


def prepare_in(operands):
    """Index lists of only plain operands, for a lookup with the pairwise result."""
    operands = tuple(operands)
    if all_plain_operands(operands) and _hashes_spread(operands):
        return frozenset(operands), operands
    return None, operands


def _hashes_spread(operands) -> bool:
    """Whether a set of these operands avoids long hash-collision chains."""
    # Any int or float at or above the modulus in magnitude sends the whole list
    # to the pairwise scan. Smaller ints hash to themselves; larger ones can share
    # a hash without bound, which makes building the set quadratic. Large floats
    # follow the same rule, although their collision chains are short.
    try:
        return max(map(abs, operands), default=0) < _MODULUS
    except TypeError:  # str or None operands
        return all(-_MODULUS < value < _MODULUS for value in operands if type(value) in _NUMBERS)


def _match_in(value, prepared) -> bool:
    hashed, operands = prepared
    if hashed is not None:
        if type(value) in _PLAIN:
            return value in hashed
        if value is MISSING:
            return None in hashed
        # Other unconverted types never equal a plain operand.
        if type(value) in _UNCONVERTED:
            return False
    for operand in operands:
        if _match_eq(value, operand):
            return True
    return False
