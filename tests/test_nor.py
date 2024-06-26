import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$nor",
        {
            "$nor": [
                {"foo": "bar", "baz": {"$ne": None}},
                {"baz": {"$gt": 2}},
            ],
        },
        [
            {"foo": "bar"},
            {"foo": "bar", "baz": 1},
            {"foo": "qux", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "bar"},
            {},
            {"foo": {"foo": "bar"}},
        ],
    ),
    (
        "nested $nor and $or",
        {
            "$nor": [
                {"foo": "bar", "baz": None},
                {
                    "$or": [
                        {"foo": "bar", "baz": {"$gt": 2}},
                        {"foo": "bar", "baz": {"$lt": 0}},
                    ]
                },
            ],
        },
        [
            {"foo": "bar"},
            {"foo": "bar", "baz": -1},
            {"foo": "bar", "baz": 1},
            {"foo": "bar", "baz": 2},
            {"foo": "bar", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "bar", "baz": 1},
            {"foo": "bar", "baz": 2},
            {},
            {"foo": {"foo": "bar"}},
        ],
    ),
    (
        "nested $nor and $and",
        {
            "$nor": [
                {
                    "$and": [
                        {"foo": "bar"},
                        {"baz": None},
                    ]
                },
                {
                    "$and": [
                        {"foo": None},
                        {"baz": "qux"},
                    ]
                },
                {
                    "$and": [
                        {"foo": "bar"},
                        {"baz": {"$gt": 2}},
                    ]
                },
                {
                    "$and": [
                        {"foo": "bar"},
                        {"baz": {"$lt": 0}},
                    ]
                },
            ],
        },
        [
            {"foo": "bar"},
            {"baz": "qux"},
            {"foo": "bar", "baz": -1},
            {"foo": "bar", "baz": 1},
            {"foo": "bar", "baz": 2},
            {"foo": "bar", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "bar", "baz": 1},
            {"foo": "bar", "baz": 2},
            {},
            {"foo": {"foo": "bar"}},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_nor(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name


def test_mgqpy_invalid_query():
    query = {"$nor": {"foo": "bar"}}
    q = Query(query)
    assert q.test({"foo": "bar"}) is False
