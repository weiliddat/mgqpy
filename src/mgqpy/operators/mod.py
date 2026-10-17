import math
from typing import List

from mgqpy.utils import is_array_index, is_finite_number


def _match_mod(doc, path: List[str], ov) -> bool:
    if not _validate_mod(ov):
        return False

    if len(path) == 0:
        if isinstance(doc, list) and any([_match_mod(d, path, ov) for d in doc]):
            return True

        if not is_finite_number(doc):
            return False

        divisor, expected_remainder = map(math.trunc, ov)
        dividend = math.trunc(doc)
        if not -(2**63) <= dividend < 2**63:
            return False
        remainder = abs(dividend) % abs(divisor)
        if dividend < 0:
            remainder = -remainder
        return remainder == expected_remainder

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_mod(doc[key], rest, ov)

    if isinstance(doc, list) and is_array_index(key):
        idx = int(key)
        if idx < len(doc):
            return _match_mod(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_mod(d, path, ov) for d in doc])

    return False


def _validate_mod(ov):
    return (
        isinstance(ov, list)
        and len(ov) == 2
        and all(is_finite_number(value) for value in ov)
        and all(-(2**63) <= math.trunc(value) < 2**63 for value in ov)
        and math.trunc(ov[0]) != 0
    )
