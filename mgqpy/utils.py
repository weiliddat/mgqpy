"""Utility helpers for mgqpy."""

import datetime
import decimal
import uuid
from typing import Any, Sequence


def coerce(a: Any, b: Any) -> tuple[Any, Any]:
    """Make *a* and *b* directly comparable by aligning their types.

    The coercion rules are intentionally conservative - we only convert
    where the *intent* is unambiguous (e.g. ISO-8601 date strings).  The
    function never raises: if conversion fails we fall back to the
    original values so the caller can attempt a normal comparison.
    """

    match (a, b):
        # one is date/datetime, other is str
        case (datetime.date() | datetime.datetime(), str()):
            return a, _try_date(b, type(a))
        case (str(), datetime.date() | datetime.datetime()):
            return _try_date(a, type(b)), b

        # one is decimal
        case (decimal.Decimal(), _):
            return a, _try_decimal(b)
        case (_, decimal.Decimal()):
            return _try_decimal(a), b

        # one is uuid
        case (uuid.UUID(), _):
            return a, _try_uuid(b)
        case (_, uuid.UUID()):
            return _try_uuid(a), b

        # default return original values
        case _:
            return a, b


# Datetime ↔︎ ISO 8601 string
def _try_date(s: str, target):
    """Attempt to convert *val* to target date or datetime"""
    try:
        if target is datetime.date:
            return datetime.date.fromisoformat(s)
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        # Not a valid ISO format – leave as string so normal
        # comparison semantics apply (and tests expecting a failure
        # still pass).
        return s


# UUID ↔︎ string
def _try_uuid(val: object):
    """Attempt to convert *val* to UUID"""
    if isinstance(val, uuid.UUID):
        return val
    if isinstance(val, str):
        try:
            return uuid.UUID(val)
        except ValueError:
            return val
    return val


# Decimal ↔︎ number / numeric-string
def _try_decimal(val: object):
    """Attempt to convert *val* to Decimal"""
    if isinstance(val, decimal.Decimal):
        return val
    if isinstance(val, (int, float, str)) and not isinstance(val, bool):
        try:
            return decimal.Decimal(str(val))
        except (decimal.InvalidOperation, ValueError):
            pass
    return val


__all__: Sequence[str] = ("coerce",)
