import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$ne str",
        {"foo": {"$ne": "bar"}},
        [
            {"foo": "bar"},
            {},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
        ],
        [
            {},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
        ],
    ),
    (
        "$ne, full object match",
        {"foo": {"$ne": {"bar": 1, " $size": 2}}},
        [
            {"foo": "bar"},
            {},
            {"foo": [{"bar": 1}, {"bar": 2}]},
            {"foo": {"bar": 1, " $size": 2}},
        ],
        [
            {"foo": "bar"},
            {},
            {"foo": [{"bar": 1}, {"bar": 2}]},
        ],
    ),
    (
        "nested object path, $ne str",
        {"foo.bar": {"$ne": "baz"}},
        [
            {"foo": {"bar": "baz"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
        [
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
    ),
    (
        "nested object path, explicit $ne empty ov",
        {"foo.bar": {"$ne": {}}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": "baz"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
        [
            {"foo": {"bar": "baz"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
    ),
    (
        "nested object path, full object match",
        {"foo.bar": {"$ne": {"baz": "qux", "$ne": "bar"}}},
        [
            {"foo": {"bar": {"baz": "qux", "$ne": "bar"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
    ),
    (
        "nested object path, full object match",
        {"foo.bar": {"$ne": {"baz": "qux"}}},
        [
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
    ),
    (
        "explicit $ne, object against null",
        {"foo.bar": {"$ne": None}},
        [
            {"foo": {"bar": None}},
            {"foo": {"bar": "baz"}},
            {"foo": None},
            {"foo": "bar"},
            {},
        ],
        [
            {"foo": {"bar": "baz"}},
        ],
    ),
    (
        "match against arrays on ov",
        {"foo.bar": {"$ne": ["baz"]}},
        [
            {"foo": {"bar": "baz"}},
            {"foo": {"bar": ["baz"]}},
            {"foo": {"bar": [["baz"]]}},
            {"foo": {"bar": ["baz", ["baz"]]}},
            {"foo": {"bar": ["baz", "bar"]}},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
        [
            {"foo": {"bar": "baz"}},
            {"foo": {"bar": ["baz", "bar"]}},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
    ),
    (
        "match against arrays on doc",
        {"foo.bar": {"$ne": "baz"}},
        [
            {"foo": {"bar": ["bar"]}},
            {"foo": {"bar": ["baz", "bar"]}},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
        [
            {"foo": {"bar": ["bar"]}},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
    ),
    (
        "unindexed nested object path with intermediate arrays on doc",
        {"a.b.c.d": {"$ne": 1}},
        [
            {"a": {"b": {"c": [{"d": [1]}]}}},
            {"a": [{"b": [{"c": [{"d": 1}]}]}]},
            {"a": [{"b": {"c": [{"d": 1}]}}]},
            {"a": {"b": {"c": [None, {"d": 1}]}}},
            {"a": [{"b": [{"c": [{"d": 2}]}]}]},
            {"a": {}},
            {},
        ],
        [
            {"a": [{"b": [{"c": [{"d": 2}]}]}]},
            {"a": {}},
            {},
        ],
    ),
    (
        "unindexed nested object path against null",
        {"foo.bar": {"$ne": None}},
        [
            {"foo": [{"bar": "baz"}]},
            {},
            {"foo": "bar"},
            {"foo": {"bar": None}},
            {"foo": [{"bar": "qux"}]},
        ],
        [
            {"foo": [{"bar": "baz"}]},
            {"foo": [{"bar": "qux"}]},
        ],
    ),
    (
        "indexed nested object path with intermediate arrays on doc",
        {"foo.1.bar": {"$ne": "baz"}},
        [
            {"foo": [{}, {"bar": "baz"}]},
            {"foo": [{"bar": "baz"}, {}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
        [
            {"foo": [{"bar": "baz"}, {}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
    ),
    (
        "nested arrays on doc",
        {"foo.bar.baz": {"$ne": "qux"}},
        [
            {"foo": [{"bar": [{"baz": "qux"}]}]},
            {"foo": [{"bar": [{"baz": "jaz"}]}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "baz"}]},
        ],
        [
            {"foo": [{"bar": [{"baz": "jaz"}]}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "baz"}]},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_ne(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name
