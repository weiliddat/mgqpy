import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$size",
        {"foo": {"$size": 2}},
        [
            {"foo": [1, "a"]},
            {"foo": [{}, {}]},
            {"foo": [1, 2, 3]},
            {"foo": []},
            {"foo": None},
        ],
        [
            {"foo": [1, "a"]},
            {"foo": [{}, {}]},
        ],
    ),
    (
        "$size 0",
        {"foo": {"$size": 0}},
        [
            {"foo": [1, "a"]},
            {"foo": [{}, {}]},
            {"foo": [1, 2, 3]},
            {"foo": []},
            {"foo": None},
        ],
        [
            {"foo": []},
        ],
    ),
    (
        "$size dict access",
        {"foo.bar": {"$size": 2}},
        [
            {"foo": {"bar": [1, 2]}},
            {"foo": [{"bar": {}}, {"bar": [2, 2]}]},
            {"foo": {"bar": [{}, 2, {"g": "f", "a": "b", "c": "d"}]}},
            {"foo": {}},
            {"foo": [{"bar": [1]}, {"bar": [2]}]},
        ],
        [
            {"foo": {"bar": [1, 2]}},
            {"foo": [{"bar": {}}, {"bar": [2, 2]}]},
        ],
    ),
    (
        "$size list access",
        {"foo.0.bar": {"$size": 2}},
        [
            {"foo": [{"bar": [1, 2]}, {"bar": [1, 2, 3]}]},
            {"foo": [{"bar": [1, 2, 3]}, {"bar": [1, 2]}]},
            {"foo": {"bar": [1, 2]}},
        ],
        [
            {"foo": [{"bar": [1, 2]}, {"bar": [1, 2, 3]}]},
        ],
    ),
    (
        "$size with float",
        {"foo": {"$size": 2.0}},
        [
            {"foo": [1, "a"]},
            {"foo": [{}, {}]},
            {"foo": [1, 2, 3]},
            {"foo": []},
            {"foo": None},
        ],
        [
            {"foo": [1, "a"]},
            {"foo": [{}, {}]},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_size(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name


def test_mgqpy_invalid_query():
    query = {"foo": {"$size": "2"}}
    q = Query(query)
    assert q.match({"foo": ["bar", "baz"]}) is False
