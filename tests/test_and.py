import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

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
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name


def test_mgqpy_invalid_query():
    query = {"$and": {"foo": "bar"}}
    q = Query(query)
    assert q.test({"foo": "bar"}) is False
