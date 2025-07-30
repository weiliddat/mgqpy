"""Utility helpers for mgqpy."""

import datetime
import decimal
import uuid
from typing import Any, Sequence


def coerce(a: Any, b: Any) -> tuple[Any, Any]:
    """Make *a* and *b* directly comparable by aligning their types.

    The coercion rules are intentionally conservative – we only convert
    where the *intent* is unambiguous (e.g. ISO-8601 date strings).  The
    function never raises: if conversion fails we fall back to the
    original values so the caller can attempt a normal comparison.
    """

    # Datetime ↔︎ ISO 8601 string
    def _parse_date(s: str, target):
        try:
            if target is datetime.date:
                return datetime.date.fromisoformat(s)
            return datetime.datetime.fromisoformat(s)
        except ValueError:
            # Not a valid ISO format – leave as string so normal
            # comparison semantics apply (and tests expecting a failure
            # still pass).
            return s

    # If one side is date/datetime and the other a string → parse.
    if isinstance(a, (datetime.date, datetime.datetime)) and isinstance(b, str):
        b = _parse_date(b, type(a))
        return a, b

    if isinstance(b, (datetime.date, datetime.datetime)) and isinstance(a, str):
        a = _parse_date(a, type(b))
        return a, b

    # Only attempt Decimal coercion when at least *one* operand is already a
    # Decimal instance.
    if isinstance(a, decimal.Decimal) or isinstance(b, decimal.Decimal):
        a = a if isinstance(a, decimal.Decimal) else _try_decimal(a)[1]
        b = b if isinstance(b, decimal.Decimal) else _try_decimal(b)[1]
        return a, b

    # UUID ↔︎ string
    def _to_uuid(val: object):
        if isinstance(val, uuid.UUID):
            return val
        if isinstance(val, str):
            try:
                return uuid.UUID(val)
            except ValueError:
                return val
        return val

    if isinstance(a, uuid.UUID) ^ isinstance(b, uuid.UUID):
        return _to_uuid(a), _to_uuid(b)

    # If no rule matched – leave untouched
    return a, b


# Decimal ↔︎ number / numeric-string
def _try_decimal(val: object):
    """Attempt to convert *val* to Decimal; returns (success, value)."""
    if isinstance(val, decimal.Decimal):
        return True, val
    if isinstance(val, (int, float, str)) and not isinstance(val, bool):
        try:
            return True, decimal.Decimal(str(val))
        except (decimal.InvalidOperation, ValueError):
            pass
    return False, val


__all__: Sequence[str] = ("coerce",)
