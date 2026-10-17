from .eq_ne_not import _match_eq


def _match_in(value, operands) -> bool:
    for operand in operands:
        if _match_eq(value, operand):
            return True
    return False
