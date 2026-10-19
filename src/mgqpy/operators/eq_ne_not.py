from mgqpy.operators.regex import _Regex
from mgqpy.path import MISSING
from mgqpy.utils import coerce


def _match_eq(value, operand) -> bool:
    if type(value) in (int, float) and type(operand) in (int, float):
        return value == operand
    if value is MISSING:
        return operand is None
    if isinstance(operand, _Regex):
        if isinstance(value, str):
            return operand.matcher.search(value)
        operand = operand.literal
    value, operand = coerce(value, operand)
    return value == operand
