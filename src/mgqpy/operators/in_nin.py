from ..comparison import _PLAIN, _UNCONVERTED, all_plain_operands
from ..path import MISSING
from .eq_ne_not import _match_eq


def prepare_in(operands):
    """Index lists of only plain operands, for a lookup with the pairwise result."""
    operands = tuple(operands)
    if all_plain_operands(operands):
        return frozenset(operands), operands
    return None, operands


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
