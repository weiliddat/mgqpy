import math

from mgqpy.utils import is_finite_number


def _match_mod(value, operand) -> bool:
    if not is_finite_number(value):
        return False
    divisor, expected_remainder = operand
    dividend = math.trunc(value)
    if not -(2**63) <= dividend < 2**63:
        return False
    remainder = abs(dividend) % divisor
    if dividend < 0:
        remainder = -remainder
    return remainder == expected_remainder


def _validate_mod(value):
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(is_finite_number(item) for item in value)
        and all(-(2**63) <= math.trunc(item) < 2**63 for item in value)
        and math.trunc(value[0]) != 0
    )
