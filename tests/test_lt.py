import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$lt number",
        {"foo": {"$lt": 1}},
        [
            {"foo": 0},
            {"foo": 1},
            {"foo": 2},
            {"foo": "0"},
            {"foo": "1"},
            {"foo": "2"},
            {},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
            {"foo": None},
        ],
        [
            {"foo": 0},
        ],
    ),
    (
        "$lt str",
        {"foo": {"$lt": "bar"}},
        [
            {"foo": 0},
            {"foo": 1},
            {"foo": 2},
            {},
            {"foo": "baa"},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
            {"foo": None},
        ],
        [
            {"foo": "baa"},
        ],
    ),
    (
        "$lt str",
        {"foo": {"$lt": "1"}},
        [
            {"foo": 0},
            {"foo": 1},
            {"foo": 2},
            {},
            {"foo": "0"},
            {"foo": "baa"},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
            {"foo": None},
        ],
        [
            {"foo": "0"},
        ],
    ),
    (
        "$lt none",
        {"foo": {"$lt": None}},
        [
            {"foo": -1},
            {"foo": 0},
            {"foo": 1},
            {},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
            {"foo": None},
        ],
        [],
    ),
    (
        "nested object path, $lt number",
        {"foo.bar": {"$lt": 1}},
        [
            {"foo": {"bar": 0}},
            {"foo": {"bar": 1}},
            {"foo": {"bar": 2}},
            {},
            {"foo": {"bar": "baz"}},
            {"foo": None},
        ],
        [
            {"foo": {"bar": 0}},
        ],
    ),
    (
        "nested object path, $lt str",
        {"foo.bar": {"$lt": "baj"}},
        [
            {"foo": {"bar": 0}},
            {"foo": {"bar": 1}},
            {"foo": {"bar": 2}},
            {},
            {"foo": {"bar": "baa"}},
            {"foo": {"bar": "baj"}},
            {"foo": {"bar": "baz"}},
            {"foo": None},
        ],
        [
            {"foo": {"bar": "baa"}},
        ],
    ),
    (
        "nested object path, $lt None",
        {"foo.bar": {"$lt": None}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": []}},
            {"foo": {"bar": -1}},
            {"foo": {"bar": 0}},
            {"foo": {"bar": 1}},
            {},
            {"foo": {"bar": "baz"}},
            {"foo": None},
        ],
        [],
    ),
    (
        "intermediate indexed array, $lt number",
        {"foo.1.bar": {"$lt": 1}},
        [
            {"foo": [{}, {"bar": 0}]},
            {"foo": [{"bar": 2}, {}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "baz"}]},
            {"foo": None},
        ],
        [
            {"foo": [{}, {"bar": 0}]},
        ],
    ),
    (
        "doc leaf array, $lt number",
        {"foo.bar": {"$lt": 1}},
        [
            {"foo": {"bar": [0, 1]}},
            {"foo": {"bar": [1, 2]}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
            {"foo": None},
        ],
        [
            {"foo": {"bar": [0, 1]}},
        ],
    ),
    (
        "unindexed nested object path with intermediate arrays on doc",
        {"a.b.c": {"$lt": 1}},
        [
            {"a": [{"b": [{"c": 0}]}]},
            {"a": [{"b": [{"c": 2}]}]},
            {},
            {"a": {"b": "bar"}},
            {"a": None},
        ],
        [
            {"a": [{"b": [{"c": 0}]}]},
        ],
    ),
    (
        "nested object path, object comparison",
        {"foo.bar": {"$lt": {"baz": "qux"}}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": {"baa": "zap"}}},
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "bux"}}},
            {"foo": {"bar": {"baz": "zap"}}},
            {"foo": {"bar": {"bla": "jaz"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": {"baa": "zap"}}},
            {"foo": {"bar": {"baz": "bux"}}},
        ],
    ),
    (
        "nested object path, object comparison many keys",
        {"foo.bar": {"$lt": {"a": "b", "c": "d"}}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": {"a": "a"}}},
            {"foo": {"bar": {"a": "b"}}},
            {"foo": {"bar": {"a": "c"}}},
            {"foo": {"bar": {"b": "a"}}},
            {"foo": {"bar": {"a": "b", "b": "a"}}},
            {"foo": {"bar": {"a": "b", "c": "c"}}},
            {"foo": {"bar": {"a": "b", "c": "d"}}},
            {"foo": {"bar": {"a": "b", "c": "e"}}},
            {"foo": {"bar": {"a": "b", "c": "d", "e": "f"}}},
        ],
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": {"a": "a"}}},
            {"foo": {"bar": {"a": "b"}}},
            {"foo": {"bar": {"a": "b", "b": "a"}}},
            {"foo": {"bar": {"a": "b", "c": "c"}}},
        ],
    ),
    (
        "nested object path, object comparison empty ov",
        {"foo.bar": {"$lt": {}}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": None}},
            {"foo": {"bar": 1}},
            {"foo": {"bar": "baz"}},
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
        ],
        [],
    ),
    (
        "nested object path, list comparison",
        {"foo.bar": {"$lt": ["bar", "baz"]}},
        [
            {"foo": {"bar": ["baa"]}},
            {"foo": {"bar": ["bar"]}},
            {"foo": {"bar": ["zzz"]}},
            {"foo": {"bar": ["bar", "baz"]}},
            {"foo": {"bar": ["baz", "bar"]}},
            {"foo": {"bar": ["baa", "bzz"]}},
            {"foo": {"bar": ["bzz", "baa"]}},
            {"foo": {"bar": ["bar", "baz", "qux"]}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [
            {"foo": {"bar": ["baa"]}},
            {"foo": {"bar": ["bar"]}},
            {"foo": {"bar": ["baa", "bzz"]}},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_lt(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name
