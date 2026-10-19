"""Exact built-ins and equivalent subclasses must have the same query semantics."""

from datetime import date, datetime, timezone
from decimal import Decimal
import random
from uuid import UUID

import pytest

from mgqpy import Query
import mgqpy.comparison as comparison


# Subclasses retain their values but bypass exact-type comparison/membership paths.
GENERAL = {cls: type("General" + cls.__name__, (cls,), {})
           for cls in (int, float, str, bytes, dict, list, UUID)}


def test_bson_kind_ranks():
    assert (comparison._NULL, comparison._NUMBER, comparison._STRING,
            comparison._DOCUMENT, comparison._ARRAY, comparison._BINARY,
            comparison._BOOL, comparison._DATE, comparison._REGEX) == tuple(range(9))


def general(value):
    cls = GENERAL.get(type(value))
    if cls is None:
        return value
    if isinstance(value, dict):
        return cls((key, general(child)) for key, child in value.items())
    if isinstance(value, list):
        return cls(general(child) for child in value)
    if isinstance(value, UUID):
        return cls(int=value.int)
    return cls(value)


def outcome(query, doc):
    try:
        return Query(query).test(doc)
    except TypeError as error:
        return type(error)  # Naive/aware datetime ordering must still raise.


@pytest.mark.parametrize("mode", ["comparison", "all"])
def test_fast_paths_agree_with_general_paths(mode):
    rng = random.Random(4361)
    uid = UUID("0123456789abcdef0123456789abcdef")
    simple = [-1, 0, 1, 2**60 + 1, 1.0, float(2**60),
              "1", "a", "3.14", "2024-08-01", uid.hex]
    scalars = simple + [None, False, True, float("nan"), -float("inf"), float("inf"),
                        b"", b"z", b"aa", Decimal("3.14"), Decimal("NaN"), Decimal("sNaN"),
                        date(2024, 8, 1), datetime(2024, 8, 1),
                        datetime(2024, 8, 1, tzinfo=timezone.utc), uid]
    if mode == "comparison":
        values = scalars + [rng.choices(scalars, k=rng.randrange(4)) for _ in range(40)]
        for _ in range(40):
            a, b = rng.choices(scalars, k=2)
            values.extend(({"a": a, "z": b}, {"z": b, "a": a}))
        pairs = [(value, value) for value in values]
        for a in scalars:
            for b in scalars:
                pairs.extend(((a, b), ({"a": a}, {"a": b}), ([a], [b])))
        pairs += [(a, b) for a, b in (rng.choices(values, k=2) for _ in range(400))]
        for value, operand in pairs:
            for op in ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin"):
                argument = [operand] if op in ("$in", "$nin") else operand
                query, doc = {"x.0": {op: argument}}, {"x": [value]}
                assert outcome(query, doc) == outcome(general(query), general(doc)), (op, value, operand)
    else:
        for length in (0, 1, 31, 32, 33, 127, 128, 129, 160):
            for special in scalars + [{"a": [1]}, [1, 2]]:
                values = rng.choices(simple, k=length)
                if values:
                    values[rng.choice([0, min(31, length - 1), min(128, length - 1), length - 1])] = special
                for operands in ([1, "1"], [simple[0], special], ["absent", special],
                                 ["2024-08-01", "3.14", uid.hex], [1, 1]):
                    query = {"x.y": {"$all": operands}}
                    for leaves in ([values], [values[:32], values[32:]], [values[32:], values[:32]]):
                        doc = {"x": [{"y": leaf} for leaf in leaves]}
                        assert outcome(query, doc) == outcome(general(query), general(doc)), (length, operands, values)
