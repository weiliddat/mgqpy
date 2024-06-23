import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "explicit $eq",
        {"foo": {"$eq": "bar"}},
        [{"foo": "bar"}, {}, {"foo": "baz"}, {"foo": {"foo": "bar"}}],
        [{"foo": "bar"}],
    ),
    (
        "implicit $eq",
        {"foo": "bar"},
        [{"foo": "bar"}, {}, {"foo": "baz"}, {"foo": {"foo": "bar"}}],
        [{"foo": "bar"}],
    ),
    (
        "implicit $eq, full object match",
        {"foo": {"bar": 1, " $size": 2}},
        [
            {"foo": "bar"},
            {},
            {"foo": [{"bar": 1}, {"bar": 2}]},
            {"foo": {"bar": 1, " $size": 2}},
        ],
        [{"foo": {"bar": 1, " $size": 2}}],
    ),
    (
        "explicit $eq, full object match",
        {"foo": {"$eq": {"bar": 1, " $size": 2}}},
        [
            {"foo": "bar"},
            {},
            {"foo": [{"bar": 1}, {"bar": 2}]},
            {"foo": {"bar": 1, " $size": 2}},
        ],
        [{"foo": {"bar": 1, " $size": 2}}],
    ),
    (
        "nested object path, explicit $eq",
        {"foo.bar": {"$eq": "baz"}},
        [
            {"foo": {"bar": "baz"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
        [{"foo": {"bar": "baz"}}],
    ),
    (
        "nested object path, explicit $eq empty ov",
        {"foo.bar": {}},
        [
            {"foo": {"bar": {}}},
            {"foo": {"bar": "baz"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
        [
            {"foo": {"bar": {}}},
        ],
    ),
    (
        "nested object path, implicit $eq",
        {"foo.bar": "baz"},
        [
            {"foo": {"bar": "baz"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "qux"}},
        ],
        [{"foo": {"bar": "baz"}}],
    ),
    (
        "nested object path, full object match",
        {"foo.bar": {"baz": "qux", "$eq": "bar"}},
        [
            {"foo": {"bar": {"baz": "qux", "$eq": "bar"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [{"foo": {"bar": {"baz": "qux", "$eq": "bar"}}}],
    ),
    (
        "nested object path, full object match",
        {"foo.bar": {"baz": "qux"}},
        [
            {"foo": {"bar": {"baz": "qux"}}},
            {"foo": {"bar": {"baz": "qux", "bla": "jaz"}}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz"}},
        ],
        [{"foo": {"bar": {"baz": "qux"}}}],
    ),
    (
        "implicit $eq, object against null",
        {"foo.bar": None},
        [
            {"foo": {"bar": None}},
            {"foo": {"bar": "baz"}},
            {"foo": None},
            {"foo": "bar"},
            {},
        ],
        [{"foo": {"bar": None}}, {"foo": None}, {"foo": "bar"}, {}],
    ),
    (
        "explicit $eq, object against null",
        {"foo.bar": {"$eq": None}},
        [
            {"foo": {"bar": None}},
            {"foo": {"bar": "baz"}},
            {"foo": None},
            {"foo": "bar"},
            {},
        ],
        [{"foo": {"bar": None}}, {"foo": None}, {"foo": "bar"}, {}],
    ),
    (
        "match against arrays on ov",
        {"foo.bar": ["baz"]},
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
            {"foo": {"bar": ["baz"]}},
            {"foo": {"bar": [["baz"]]}},
            {"foo": {"bar": ["baz", ["baz"]]}},
        ],
    ),
    (
        "match against arrays on doc",
        {"foo.bar": "baz"},
        [
            {"foo": {"bar": ["bar"]}},
            {"foo": {"bar": ["baz", "bar"]}},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
        [{"foo": {"bar": ["baz", "bar"]}}],
    ),
    (
        "unindexed nested object path with intermediate arrays on doc",
        {"a.b.c.d": 1},
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
            {"a": {"b": {"c": [{"d": [1]}]}}},
            {"a": [{"b": [{"c": [{"d": 1}]}]}]},
            {"a": [{"b": {"c": [{"d": 1}]}}]},
            {"a": {"b": {"c": [None, {"d": 1}]}}},
        ],
    ),
    (
        "unindexed nested object path against null",
        {"foo.bar": None},
        [
            {"foo": [{"bar": "baz"}]},
            {},
            {"foo": "bar"},
            {"foo": {"bar": None}},
            {"foo": [{"bar": "qux"}]},
        ],
        [{}, {"foo": "bar"}, {"foo": {"bar": None}}],
    ),
    (
        "indexed nested object path with intermediate arrays on doc",
        {"foo.1.bar": "baz"},
        [
            {"foo": [{}, {"bar": "baz"}]},
            {"foo": [{"bar": "baz"}, {}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "qux"}]},
        ],
        [{"foo": [{}, {"bar": "baz"}]}],
    ),
    (
        "nested arrays on doc",
        {"foo.bar.baz": "qux"},
        [
            {"foo": [{"bar": [{"baz": "qux"}]}]},
            {},
            {"foo": "bar"},
            {"foo": [{"bar": "baz"}]},
        ],
        [{"foo": [{"bar": [{"baz": "qux"}]}]}],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_eq(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name
