import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$gte number",
        {"foo": {"$gte": 1}},
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
        [{"foo": 1}, {"foo": 2}],
    ),
    (
        "$gte str",
        {"foo": {"$gte": "bar"}},
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
        [{"foo": "bar"}, {"foo": "baz"}],
    ),
    (
        "$gte str",
        {"foo": {"$gte": "1"}},
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
            {"foo": "bar"},
            {"foo": "baz"},
        ],
    ),
    (
        "$gte none",
        {"foo": {"$gte": None}},
        [
            {"foo": -1},
            {"foo": 0},
            {"foo": 1},
            {},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
            {"foo": None},
        ],
        [{}, {"foo": None}],
    ),
    (
        "nested object path, $gte number",
        {"foo.bar": {"$gte": 1}},
        [
            {"foo": {"bar": 0}},
            {"foo": {"bar": 1}},
            {"foo": {"bar": 2}},
            {},
            {"foo": {"bar": "baz"}},
            {"foo": None},
        ],
        [
            {"foo": {"bar": 1}},
            {"foo": {"bar": 2}},
        ],
    ),
    (
        "nested object path, $gte str",
        {"foo.bar": {"$gte": "baj"}},
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
            {"foo": {"bar": "baj"}},
            {"foo": {"bar": "baz"}},
        ],
    ),
    (
        "nested object path, $gte None",
        {"foo.bar": {"$gte": None}},
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
        [
            {},
            {"foo": None},
        ],
    ),
    (
        "intermediate indexed array, $gte number",
        {"foo.1.bar": {"$gte": 1}},
        [
            {"foo": [{}, {"bar": 2}]},
            {"foo": [{"bar": 2}, {}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "baz"}]},
            {"foo": None},
        ],
        [
            {"foo": [{}, {"bar": 2}]},
        ],
    ),
    (
        "doc leaf array, $gte number",
        {"foo.bar": {"$gte": 1}},
        [
            {"foo": {"bar": [0, -1]}},
            {"foo": {"bar": [2, 1]}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
            {"foo": None},
        ],
        [
            {"foo": {"bar": [2, 1]}},
        ],
    ),
    (
        "unindexed nested object path with intermediate arrays on doc",
        {"a.b.c": {"$gte": 1}},
        [
            {"a": [{"b": [{"c": 0}]}]},
            {"a": [{"b": [{"c": [1]}]}]},
            {"a": [{"b": [{"c": 2}]}]},
            {},
            {"a": {"b": "bar"}},
            {"a": None},
        ],
        [
            {"a": [{"b": [{"c": [1]}]}]},
            {"a": [{"b": [{"c": 2}]}]},
        ],
    ),
    (
        "nested object path, object comparison",
        {"foo.bar": {"$gte": {"baz": "qux"}}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": {"baa": "zap"}}},
            {"foo": {"bar": {"baz": "bux"}}},
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "zap"}}},
            {"foo": {"bar": {"bla": "jaz"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "zap"}}},
            {"foo": {"bar": {"bla": "jaz"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
        ],
    ),
    (
        "nested object path, object comparison empty ov",
        {"foo.bar": {"$gte": {}}},
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
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
        ],
    ),
    (
        "nested object path, object comparison many keys",
        {"foo.bar": {"$gte": {"a": "b", "c": "d"}}},
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
            {"foo": {"bar": {"a": "b", "d": "a"}}},
            {"foo": {"bar": {"a": "b", "c": "d", "e": "f"}}},
        ],
        [
            {"foo": {"bar": {"a": "c"}}},
            {"foo": {"bar": {"b": "a"}}},
            {"foo": {"bar": {"a": "b", "c": "d"}}},
            {"foo": {"bar": {"a": "b", "c": "e"}}},
            {"foo": {"bar": {"a": "b", "d": "a"}}},
            {"foo": {"bar": {"a": "b", "c": "d", "e": "f"}}},
        ],
    ),
    (
        "nested object path, list comparison",
        {"foo.bar": {"$gte": ["bar", "baz"]}},
        [
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
            {"foo": {"bar": ["zzz"]}},
            {"foo": {"bar": ["bar", "baz"]}},
            {"foo": {"bar": ["baz", "bar"]}},
            {"foo": {"bar": ["bzz", "baa"]}},
            {"foo": {"bar": ["bar", "baz", "qux"]}},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_gte(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name
