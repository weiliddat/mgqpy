import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$or",
        {
            "$or": [
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
            {"foo": "bar", "baz": 1},
            {"foo": "qux", "baz": 3},
        ],
    ),
    (
        "nested $or",
        {
            "$or": [
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
            {"foo": "bar"},
            {"foo": "bar", "baz": -1},
            {"foo": "bar", "baz": 3},
        ],
    ),
    (
        "nested $or and $and",
        {
            "$or": [
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
            {"foo": "bar"},
            {"baz": "qux"},
            {"foo": "bar", "baz": -1},
            {"foo": "bar", "baz": 3},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_or(test_db, benchmark, name, query, input, expected):
    q = Query(query)
    mongo_expected = get_mongo_results(test_db, input, q)
    assert expected == mongo_expected, name
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name
