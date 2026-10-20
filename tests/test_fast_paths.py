"""Exact built-ins and equivalent subclasses must have the same query semantics."""

from datetime import date, datetime, timezone
from decimal import Decimal
import random
import sys
from uuid import UUID

import pytest

from mgqpy import Query
import mgqpy.comparison as comparison
from mgqpy.operators.in_nin import prepare_in


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


class ShiftedIterList(list):
    """Iterates as each stored item + 1."""

    def __iter__(self):
        return (item + 1 for item in list.__iter__(self))


def test_list_operand_subclasses_are_iterated_once_into_a_plain_list():
    # The query snapshot iterates the operands once; matching uses that plain list.
    assert Query({"x": {"$in": ShiftedIterList([1])}}).test({"x": 2})
    assert not Query({"x": {"$in": ShiftedIterList([1])}}).test({"x": 3})
    assert not Query({"x": {"$nin": ShiftedIterList([1])}}).test({"x": 2})
    assert Query({"x": {"$nin": ShiftedIterList([1])}}).test({"x": 3})
    assert Query({"x": {"$all": ShiftedIterList([1, 2])}}).test({"x": [2, 3]})
    assert not Query({"x": {"$all": ShiftedIterList([1, 2])}}).test({"x": [3, 4]})


@pytest.mark.parametrize("operands", [[i * sys.hash_info.modulus for i in range(1, 4)],
                                      [1e100, None], [1e100, "a"], [None, -1e100],
                                      [sys.hash_info.modulus, "a"], ["a", 2.0 ** 61]])
def test_membership_leaves_large_numbers_unhashed(operands):
    # One rule for every list: a number at or above the hash modulus in
    # magnitude keeps the whole list on the pairwise scan. Such ints can share
    # one hash, which would make building a hash set quadratic.
    assert prepare_in(operands)[0] is None
    number = next(value for value in operands if isinstance(value, (int, float)))
    query = Query({"x": {"$in": operands}})
    assert query.test({"x": number}) and query.test({"x": int(number)})
    assert not query.test({"x": int(number) + 1})
    assert query.test({"x": "a"}) is ("a" in operands)
    assert query.test({}) is (None in operands)
