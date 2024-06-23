import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$not",
        {
            "foo": {"$not": {"$eq": "bar"}},
        },
        [
            {"foo": "bar"},
            {"foo": "qux", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "qux", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
    ),
    (
        "$not multiple conditions",
        {
            "foo": {
                "$not": {
                    "$in": ["bar", "baz"],
                    "$ne": "qux",
                }
            },
        },
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "qux", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "qux", "baz": 3},
            {},
            {"foo": {"foo": "bar"}},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_not(test_db, benchmark, name, query, input, expected):
    q = Query(query)
    mongo_expected = get_mongo_results(test_db, input, q)
    assert expected == mongo_expected, name
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name
