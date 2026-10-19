"""One equality contract, reused by negation and membership."""

import re

import pytest

from .helpers import assert_matches


@pytest.mark.parametrize("operand,values,hits", [
    ("bar", ["bar", "baz", {"x": "bar"}, ["baz", "bar"]], [0, 3]),
    (1, [1, 1.0, True, False, "1", [True], [1], [[1]]], [0, 1, 6]),
    (True, [True, 1, 1.0, False, [1], [True]], [0, 5]),
    (0, [False, 0, 0.0, None, [False], [0]], [1, 2, 5]),
    ({}, [{}, [], None, [{}], {"a": 1}], [0, 3]),
    ({"a": 1, "b": 2}, [{"a": 1, "b": 2}, {"b": 2, "a": 1},
                        {"a": True, "b": 2}, {"a": 1}, [{"a": 1, "b": 2}]], [0, 4]),
    ({"a": {"b": 1, "c": 2}}, [{"a": {"b": 1, "c": 2}},
                               {"a": {"c": 2, "b": 1}}, {"a": {"b": True, "c": 2}}], [0]),
    ({"a": 1, "$eq": 2}, [{"a": 1, "$eq": 2}, {"a": 1, "$eq": 3}], [0]),
    ([1, 2], [[1, 2], [[1, 2]], [0, [1, 2]], [2, 1], [True, 2], [1]], [0, 1, 2]),
    ([], [[], [[]], [[[]]], None, {}], [0, 1]),
    (float("nan"), [float("nan"), -float("inf"), 0, float("inf"),
                    [float("nan")], [[float("nan")]]], [0, 4]),
    ([float("nan"), 2], [[float("nan"), 2], [float("nan"), 3],
                         [[float("nan"), 2]]], [0, 2]),
    ({"a": float("nan")}, [{"a": float("nan")}, {"a": 0},
                           [{"a": float("nan")}]], [0, 2]),
    (b"a", [b"a", b"b", "a", [b"a"]], [0, 3]),
])
@pytest.mark.parametrize("op", [None, "$eq", "$ne", "$in", "$nin"])
def test_equality_and_membership(test_db, operand, values, hits, op):
    documents = [{"x": value} for value in values] + [{}]
    if op in ("$ne", "$nin"):
        hits = [i for i in range(len(documents)) if i not in hits]
    expression = operand if op is None else {op: [operand] if op in ("$in", "$nin") else operand}
    assert_matches(test_db, {"x": expression}, documents, hits)


@pytest.mark.parametrize("expression,hits", [
    (None, [0, 1, 3]), ({"$eq": None}, [0, 1, 3]),
    ({"$ne": None}, [2, 4, 5]), ({"$in": [None, "a"]}, [0, 1, 2, 3]),
    ({"$nin": [None, "a"]}, [4, 5]), ({"$in": []}, []),
    ({"$nin": []}, [0, 1, 2, 3, 4, 5]),
])
def test_null_and_empty_membership(test_db, expression, hits):
    assert_matches(test_db, {"x": expression},
                   [{}, {"x": None}, {"x": "a"}, {"x": [None]}, {"x": []}, {"x": {}}], hits)


@pytest.mark.parametrize("op,hits", [("$eq", [1, 2]), ("$in", [0, 1, 2])])
def test_regex_literal_versus_membership(test_db, op, hits):
    pattern = re.compile("^a", re.I)
    expression = {op: [pattern] if op == "$in" else pattern}
    assert_matches(test_db, {"items.x": expression}, [
        {"items": [{"x": "abc"}]}, {"items": [{"x": pattern}]},
        {"items": [{"x": ["abc", pattern]}]},
        {"items": [{"x": re.compile("^a")}]}, {},
    ], hits)
