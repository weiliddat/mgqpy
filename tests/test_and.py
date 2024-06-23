import pytest

from mgqpy import Query

from .helpers import assert_mongo_behavior, get_filter_results

testcases = [
    (
        "implicit $and",
        {
            "foo": "bar",
            "baz": 2,
        },
        [
            {"foo": "bar", "baz": 2},
            {},
            {"foo": "bar"},
            {"baz": 2},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "bar", "baz": 2},
        ],
    ),
    (
        "explicit $and",
        {
            "$and": [
                {"foo": "bar"},
                {"baz": 2},
            ],
        },
        [
            {"foo": "bar", "baz": 2},
            {},
            {"foo": "bar"},
            {"baz": 2},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "bar", "baz": 2},
        ],
    ),
    (
        "nested $and",
        {
            "$and": [
                {"foo": "bar"},
                {"$and": [{"baz": 2}, {"qux": 3}]},
            ],
        },
        [
            {"foo": "bar", "baz": 2, "qux": 3},
            {},
            {"foo": "bar"},
            {"baz": 2},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "bar", "baz": 2, "qux": 3},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_and(test_db, benchmark, name, query, input, expected):
    q = Query(query)
    assert_mongo_behavior(test_db, name, input, expected, q)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name
