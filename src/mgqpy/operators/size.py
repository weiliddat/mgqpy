from mgqpy.utils import is_finite_number


def _match_size(value, operand) -> bool:
    return isinstance(value, list) and len(value) == operand


def _validate_size(value) -> bool:
    return is_finite_number(value) and 0 <= value <= 2**31 - 1 and value == int(value)
