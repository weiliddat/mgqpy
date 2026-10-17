"""Opt-in CPU-only baselines; run `uv run pytest benchmarks`."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from mgqpy import Query


CASES = [
    ("flat", {"x": 73}, {"x": 73}),
    ("deep", {"a.b.c.d.e": 73}, {"a": {"b": {"c": {"d": {"e": 73}}}}}),
    ("subdocuments", {"items.x": 73}, {"items": [{"x": i} for i in range(100)]}),
    ("large-in", {"x": {"$in": list(range(1000))}}, {"x": 999}),
    ("regex", {"x": {"$regex": "^item-[0-9]+$"}}, {"x": "item-73"}),
    ("and-or", {"$and": [{"x": {"$gt": 10}}, {"$or": [{"y": 0}, {"y": 2}]}]},
     {"x": 73, "y": 2}),
    ("indexed-eq", {"a.9.x": 73}, {"a": [{"x": i} for i in range(9)] + [{"x": 73}]}),
    ("indexed-eq-multi", {"a.73.x": 73}, {"a": [{"x": i} for i in range(100)]}),
    ("size", {"x": {"$size": 2}}, {"x": [1, 2]}),
    ("deep-size", {"a.b.c.d.e": {"$size": 2}},
     {"a": {"b": {"c": {"d": {"e": [1, 2]}}}}}),
    ("mod", {"x": {"$mod": [3, 1]}}, {"x": 73}),
    ("deep-mod", {"a.b.c.d.e": {"$mod": [3, 1]}},
     {"a": {"b": {"c": {"d": {"e": 73}}}}}),
    ("array-mod", {"x": {"$mod": [3, 1]}}, {"x": list(range(100))}),
    ("array-mod-last", {"x": {"$mod": [3, 1]}}, {"x": [0] * 99 + [1]}),
    ("ordered-document", {"x": {"a": 1, "b": [2, 3]}}, {"x": {"a": 1, "b": [2, 3]}}),
    ("array-range", {"x": {"$gt": [1, 2]}}, {"x": [1, 3]}),
    ("document-range", {"x": {"$gt": {"a": 1}}}, {"x": {"a": 2}}),
    ("all", {"x": {"$all": [72, 73]}}, {"x": list(range(100))}),
    ("all-string", {"x": {"$all": ["t72", "t73"]}},
     {"x": [f"t{i}" for i in range(100)]}),
    ("date", {"x": "2024-08-01"}, {"x": date(2024, 8, 1)}),
    ("decimal", {"x": {"$gte": "3.14"}}, {"x": Decimal("3.14")}),
    ("uuid", {"x": "0123456789abcdef0123456789abcdef"},
     {"x": UUID("0123456789abcdef0123456789abcdef")}),
]


MATCH_CASES = [(name, query, doc, True) for name, query, doc in CASES]
for op, hit, miss in (("$gt", 73, 0), ("$gte", 73, 0), ("$lt", 71, 99), ("$lte", 71, 99)):
    for direction, operand, cast in (("int-float", 72, float), ("float-int", 72.0, int)):
        query = {"x": {op: operand}}
        for shape, value, expected in (
            ("scalar", cast(hit), True),
            ("scalar-miss", cast(miss), False),
            ("array-last", [cast(miss)] * 99 + [cast(hit)], True),
            ("array-miss", [cast(miss)] * 100, False),
        ):
            MATCH_CASES.append((f"{op[1:]}-{direction}-{shape}", query, {"x": value}, expected))


for name, expression, hit, miss in (
    ("eq", 73, 73, 0), ("in", {"$in": [72, 73]}, 73, 0),
    ("exists", {"$exists": True}, None, None),
    ("size", {"$size": 2}, [1, 2], [1]),
    ("all", {"$all": [1, 2]}, [1, 2], [1]),
    ("elem-match", {"$elemMatch": {"a": 73}}, [{"a": 73}], [{"a": 0}]),
):
    prefix = {} if name == "exists" else {"y": miss}
    for position in (0, 99, None):
        values = [prefix] * 100
        if position is not None:
            values[position] = {"y": hit}
        MATCH_CASES.append((f"path-{name}-{position}", {"x.y": expression}, {"x": values}, position is not None))

MATCH_CASES.extend([
    ("numeric-field", {"x.0.y": 73}, {"x": [{"0": {"y": 73}}]}, True),
    ("indexed-miss", {"x.73.y": 73}, {"x": [{"y": 0}] * 100}, False),
    ("scalar-array-null", {"x.y": None}, {"x": [1] * 100}, False),
    ("nested-leaf", {"x": 73}, {"x": [[73]] * 100}, False),
    ("missing-null", {"a.b.c": None}, {}, True),
    ("empty-all", {"x.y": {"$all": []}}, {"x": [{"y": []}] * 100}, False),
    ("empty-all-negated", {"x.y": {"$not": {"$all": []}}}, {"x": [{"y": []}] * 100}, True),
])


for name, operand, hit, miss in (
    ("string", "target", "target", "other"),
    ("document", {"a": [1, 2]}, {"a": [1, 2]}, {"a": [1, 3]}),
    ("array", [1, {"a": 2}], [1, {"a": 2}], [1, {"a": 3}]),
    ("native-document", {"a": ["3.14"]}, {"a": [Decimal("3.14")]}, {"a": [Decimal("3.15")]}),
):
    for position in (0, 99, None):
        values = [miss] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((f"value-{name}-{position}", {"x": operand}, {"x": values}, position is not None))

for name, first, second, miss in (("number", 72, 73, 0), ("string", "t72", "t73", "other")):
    for position in (0, 98, None):
        values = [miss] * 100
        if position is None:
            values[-1] = first
        else:
            values[position:position + 2] = [first, second]
        MATCH_CASES.append((f"all-{name}-{position}", {"x": {"$all": [first, second]}},
                            {"x": values}, position is not None))

MATCH_CASES.extend([
    ("bool-not-number", {"x": 1}, {"x": True}, False),
    ("nan-equality", {"x": float("nan")}, {"x": float("nan")}, True),
    ("nan-direct-range", {"x": {"$lte": float("nan")}}, {"x": float("nan")}, True),
    ("nan-array-range", {"x.0": {"$lt": [0]}}, {"x": [[float("nan")]]}, True),
    ("type-before-key", {"x": {"$gt": {"z": 1}}}, {"x": {"a": "x"}}, True),
    ("all-scalar", {"x": {"$all": [1]}}, {"x": 1}, True),
    ("all-branches", {"x.y": {"$all": [1, 2]}}, {"x": [{"y": 1}, {"y": 2}]}, True),
    ("all-native", {"x": {"$all": ["3.14"]}}, {"x": [Decimal("3.14")]}, True),
    ("native-container-range", {"x": {"$gte": {"a": ["3.14"]}}},
     {"x": {"a": [Decimal("3.14")]}}, True),
])


@pytest.mark.parametrize("name,query,doc,expected", MATCH_CASES, ids=[case[0] for case in MATCH_CASES])
def test_match(benchmark, name, query, doc, expected):
    predicate = Query(query)
    assert benchmark(predicate.test, doc) is expected


@pytest.mark.parametrize("name,query,doc", CASES, ids=[case[0] for case in CASES])
def test_construct(benchmark, name, query, doc):
    assert benchmark(Query, query).test(doc) is True
