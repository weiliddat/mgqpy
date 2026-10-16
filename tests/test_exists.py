import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$exists true",
        {"foo": {"$exists": True}},
        [
            {"foo": "bar"},
            {"foo": None},
            {"foo": []},
            {"foo": {}},
            {"bar": "foo"},
            {},
        ],
        [
            {"foo": "bar"},
            {"foo": None},
            {"foo": []},
            {"foo": {}},
        ],
    ),
    (
        "$exists false",
        {"foo": {"$exists": False}},
        [
            {"foo": "bar"},
            {"foo": None},
            {"bar": "foo"},
            {},
        ],
        [
            {"bar": "foo"},
            {},
        ],
    ),
    (
        "$exists dict access",
        {"foo.bar": {"$exists": True}},
        [
            {"foo": {"bar": None}},
            {"foo": {"baz": 1}},
            {"foo": "bar"},
            {"foo": None},
            {},
        ],
        [
            {"foo": {"bar": None}},
        ],
    ),
    (
        "$exists through a list",
        {"foo.bar": {"$exists": True}},
        [
            {"foo": [{"baz": 1}, {"bar": None}]},
            {"foo": [{"baz": 1}]},
            {"foo": [1, "bar"]},
            {"foo": [[{"bar": 1}]]},
            {"foo": []},
        ],
        [
            {"foo": [{"baz": 1}, {"bar": None}]},
        ],
    ),
    (
        "$exists false through a list",
        {"foo.bar": {"$exists": False}},
        [
            {"foo": [{"baz": 1}, {"bar": None}]},
            {"foo": [{"baz": 1}]},
            {"foo": [[{"bar": 1}]]},
            {"foo": []},
        ],
        [
            {"foo": [{"baz": 1}]},
            {"foo": [[{"bar": 1}]]},
            {"foo": []},
        ],
    ),
    (
        "$exists list index",
        {"foo.1": {"$exists": True}},
        [
            {"foo": ["a", "b"]},
            {"foo": ["a"]},
            {"foo": {"1": "a"}},
            {"foo": [{"1": "a"}]},
        ],
        [
            {"foo": ["a", "b"]},
            {"foo": {"1": "a"}},
            {"foo": [{"1": "a"}]},
        ],
    ),
    (
        "$exists with another operator",
        {"foo": {"$exists": True, "$ne": None}},
        [
            {"foo": "bar"},
            {"foo": None},
            {},
        ],
        [
            {"foo": "bar"},
        ],
    ),
    (
        "$exists or null",
        {"$or": [{"foo": {"$exists": False}}, {"foo": None}, {"foo": ""}, {"foo": []}]},
        [
            {"foo": "bar"},
            {"foo": None},
            {"foo": ""},
            {"foo": []},
            {"foo": ["bar"]},
            {},
        ],
        [
            {"foo": None},
            {"foo": ""},
            {"foo": []},
            {},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_exists(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name
