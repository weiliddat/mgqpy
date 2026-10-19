"""Opt-in CPU-only baselines; run `uv run pytest benchmarks`."""

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


@pytest.mark.parametrize("name,query,doc,expected", MATCH_CASES, ids=[case[0] for case in MATCH_CASES])
def test_match(benchmark, name, query, doc, expected):
    predicate = Query(query)
    assert benchmark(predicate.test, doc) is expected


@pytest.mark.parametrize("name,query,doc", CASES, ids=[case[0] for case in CASES])
def test_construct(benchmark, name, query, doc):
    assert benchmark(Query, query).test(doc) is True
