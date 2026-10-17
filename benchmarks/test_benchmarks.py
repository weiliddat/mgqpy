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
]


@pytest.mark.parametrize("name,query,doc", CASES, ids=[case[0] for case in CASES])
def test_match(benchmark, name, query, doc):
    predicate = Query(query)
    assert benchmark(predicate.test, doc) is True


@pytest.mark.parametrize("name,query,doc", CASES, ids=[case[0] for case in CASES])
def test_construct(benchmark, name, query, doc):
    assert benchmark(Query, query).test(doc) is True
