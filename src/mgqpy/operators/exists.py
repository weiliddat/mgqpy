from mgqpy.path import MISSING


def _match_exists(value, operand) -> bool:
    return value is not MISSING
