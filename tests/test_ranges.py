"""Type brackets at the query boundary, BSON ordering inside containers."""

import re

import pytest

from .helpers import assert_matches


# Ordered pairs: the expected sign is independent of the implementation.
@pytest.mark.parametrize("value,operand,order", [
    (71, 72.0, -1), (72.0, 72, 0), (73.0, 72, 1),
    (2**53 + 1, float(2**53), 1), (float(2**53), 2**53 + 1, -1),
    ("baa", "bar", -1), ("bar", "bar", 0), ("baz", "bar", 1),
    (False, True, -1), (True, True, 0), (True, False, 1),
    (None, None, 0),
    ({}, {"a": 1}, -1), ({"a": 1}, {}, 1),
    ({"a": 1}, {"a": 1.0}, 0), ({"a": 1}, {"a": 2}, -1),
    ({"a": 1, "b": 2}, {"a": 1}, 1),
    ({"a": 1, "b": 2}, {"a": 1, "c": 0}, -1),
    # The value's type precedes its key, contrary to a key-first comparison.
    ({"a": "z"}, {"z": 1}, 1), ({"z": 1}, {"a": "z"}, -1),
    ({"a": 100}, {"z": 0}, -1),
    ({"a": 1, "b": 2}, {"b": 2, "a": 1}, -1),
    ({"a": {"z": 1}}, {"a": {"a": "x"}}, -1),
    ([], [1], -1), ([1, 2], [1, 2.0], 0), ([1, 2], [1, 1, 99], 1),
    ([1], [1, 0], -1), ([None], [0], -1), ([1], ["a"], -1),
    (["a"], [{}], -1), ([{}], [[]], -1), ([[]], [b"a"], -1),
    ([b"a"], [False], -1), ([False], [re.compile("a")], -1),
    ([[1, "x"]], [[1, 2]], 1),
    ([{"a": "x"}], [{"z": 1}], 1),
    ([float("nan")], [-float("inf")], -1),
    ([0], [float("nan")], 1),
    ([float("nan")], [float("nan")], 0),
    ({"a": float("nan")}, {"a": -float("inf")}, -1),
    ({"a": 0}, {"a": float("nan")}, 1),
    ({"a": [float("nan")]}, {"a": [float("nan")]}, 0),
    (b"z", b"aa", -1), (b"aa", b"ab", -1),
    ([re.compile("a")], [re.compile("a", re.I)], 1),
])
@pytest.mark.parametrize("op,orders", [("$gt", [1]), ("$gte", [0, 1]),
                                      ("$lt", [-1]), ("$lte", [-1, 0])])
def test_bson_ordering(test_db, value, operand, order, op, orders):
    # An explicit terminal index compares an array as a value, without also
    # offering its elements. Missing numeric-field alternatives cannot match
    # these non-null container operands.
    assert_matches(test_db, {"x.0": {op: operand}}, [{"x": [value]}], [0] if order in orders else [])


@pytest.mark.parametrize("op,hits", [("$gt", []), ("$gte", []), ("$lt", []), ("$lte", [])])
def test_scalar_type_brackets(test_db, op, hits):
    assert_matches(test_db, {"x": {op: 1}},
                   [{"x": True}, {"x": False}, {"x": "2"}, {"x": None}, {}], hits)


@pytest.mark.parametrize("operand,op,hits", [
    (float("nan"), "$gt", []), (float("nan"), "$lt", []),
    (float("nan"), "$gte", [0]), (float("nan"), "$lte", [0]),
    (0, "$gt", [3, 4]), (0, "$gte", [3, 4]),
    (0, "$lt", [1, 2]), (0, "$lte", [1, 2]),
    (None, "$gt", []), (None, "$lt", []),
    (None, "$gte", [5, 6]), (None, "$lte", [5, 6]),
])
def test_direct_nan_and_null_ranges(test_db, operand, op, hits):
    assert_matches(test_db, {"x": {op: operand}}, [
        {"x": float("nan")}, {"x": -float("inf")}, {"x": -1},
        {"x": 1}, {"x": float("inf")}, {"x": None}, {},
    ], hits)


@pytest.mark.parametrize("op,hits", [("$gt", [2, 3]), ("$gte", [1, 2, 3]),
                                    ("$lt", [0, 3]), ("$lte", [0, 1, 3])])
def test_range_arrays_and_deep_paths(test_db, op, hits):
    assert_matches(test_db, {"a.b.c": {op: 72}}, [
        {"a": [{"b": {"c": 71.0}}]}, {"a": {"b": [{"c": 72.0}]}},
        {"a": {"b": {"c": 73.0}}}, {"a": [{"b": [{"c": [71, 73]}]}]},
        {"a": [{"b": [{"c": [[73]]}]}]}, {},
    ], hits)
