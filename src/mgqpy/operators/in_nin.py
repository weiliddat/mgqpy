import operator

from ..comparison import HASHABLE, UNEQUAL_TO_HASHABLE
from ..path import MISSING
from .eq_ne_not import _match_eq


def prepare_in(operands):
    """Index operand lists made only of exact scalars, for an equivalent lookup."""
    operands = tuple(operands)
    # NaN is the only such value unequal to itself.
    if HASHABLE.issuperset(map(type, operands)) and all(map(operator.eq, operands, operands)):
        return frozenset(operands), operands
    return None, operands


def _match_in(value, prepared) -> bool:
    hashed, operands = prepared
    if hashed is not None:
        if type(value) in HASHABLE:
            return value in hashed
        if value is MISSING:
            return None in hashed
        if type(value) in UNEQUAL_TO_HASHABLE:
            return False
    for operand in operands:
        if _match_eq(value, operand):
            return True
    return False
