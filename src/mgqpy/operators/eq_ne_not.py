from mgqpy.operators.regex import _Regex
from mgqpy.comparison import equal


def _match_eq(value, operand) -> bool:
    if isinstance(operand, _Regex):
        if isinstance(value, str):
            return operand.matcher.search(value)
        operand = operand.literal
    return equal(value, operand)
