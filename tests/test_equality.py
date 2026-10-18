"""One equality contract, reused by negation and membership."""

from datetime import date, datetime, timezone
from decimal import Decimal
from random import Random
import re
from uuid import UUID

import mgqpy
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


def test_prefilter_generated_answers_and_errors_match_exact_path(monkeypatch):
    """Compare public results with certification disabled, including unsafe tails."""
    from .test_logical import BrokenNumber, BrokenTail

    class List(list):
        def __eq__(self, other):
            return False

    class Dict(dict):
        def __eq__(self, other):
            return False

    class Int(int):
        pass

    class Str(str):
        pass

    class Wrapped:
        def __eq__(self, other):
            return other == 1

    error = RuntimeError("unread tail")
    uid = UUID("0123456789abcdef0123456789abcdef")
    pairs = [(date(2024, 8, 1), "2024-08-01"),
             (datetime(2024, 8, 1, tzinfo=timezone.utc), "2024-08-01"),
             (uid, str(uid)), (Decimal("0.1"), 0.1),
             (Decimal("3"), 3), (Decimal("3"), "3"),
             (float("nan"), float("nan")), (Decimal("NaN"), float("nan")),
             (Decimal("sNaN"), float("nan")), (True, 1),
             ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
             (List([1]), [1]), (Dict(a=1), {"a": 1}),
             (Int(1), 1), (Str("a"), "a"), (Wrapped(), 1),
             (BrokenNumber(1), 1)]
    samples = []
    for a, b in pairs:
        for a, b in ((a, b), (b, a)):
            for wrap in (lambda v: [v], lambda v: {"a": [v]},
                         lambda v: [{"a": v}]):
                value, operand = wrap(a), wrap(b)
                for values in ([value, BrokenNumber(9)], [None, value],
                               [None, value, BrokenNumber(9)],
                               [None, BrokenNumber(9), value],
                               BrokenTail([None, value], error)):
                    samples.append((operand, values))

    rng = Random(4361)
    leaves = [None, True, False, -1, 0, 1, 1.0, 0.1, "a", "3", b"a",
              float("nan"), float("inf"), Decimal("3"), Decimal("sNaN"),
              date(2024, 8, 1), "2024-08-01", uid, str(uid), Int(1), Str("a")]

    def nested(depth):
        if not depth or rng.random() < .5:
            return rng.choice(leaves)
        if rng.random() < .5:
            return [nested(depth - 1) for _ in range(rng.randrange(4))]
        return {key: nested(depth - 1)
                for key in rng.sample(["a", "b", "0", ""], rng.randrange(4))}

    for i in range(600):
        operand = [nested(3)] if i % 2 else {"a": nested(3)}
        values = [nested(3) for _ in range(rng.choice([0, 1, 2, 5, 32, 100]))]
        if values and i % 3:
            values[rng.randrange(len(values))] = operand
        samples.append((operand, values))
    # A bounded certificate must not turn an irrelevant cyclic tail into an error.
    cycle = []
    cycle.append(cycle)
    samples += [([1], [0, [2], cycle]), ([1], [0, [1], cycle]),
                ([1, 2], [1, 2]), ([], []), ({}, [{}, BrokenNumber(9)])]
    deep = [1]
    for _ in range(12):
        deep = [deep]
    samples.append((deep, [0, deep]))

    def outcome(predicate, document):
        try:
            return predicate.test(document)
        except Exception as error:
            return type(error), error.args

    certificate = mgqpy._python_equality_safe
    for operand, values in samples:
        for expression in (operand, {"$eq": operand}, {"$ne": operand},
                           {"$not": {"$eq": operand}}, {"$all": [operand]}):
            for path, document in (("x", {"x": values}),
                                   ("x.y", {"x": [{"y": values}]}),
                                   ("x.0.", {"x": [values]}),
                                   ("x.0", {"x": [values]})):
                query = {path: expression}
                monkeypatch.setattr(mgqpy, "_python_equality_safe", certificate)
                actual = outcome(mgqpy.Query(query), document)
                monkeypatch.setattr(mgqpy, "_python_equality_safe", lambda _: False)
                expected = outcome(mgqpy.Query(query), document)
                assert actual == expected, (query, document, actual, expected)
