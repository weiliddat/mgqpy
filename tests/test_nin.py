import pytest

from mgqpy import Query

from .helpers import assert_mongo_behavior, get_filter_results

testcases = [
    (
        "$nin list of str",
        {
            "foo": {"$nin": ["bar", "baz"]},
        },
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": ["qux", "baz"]},
            {},
            {"foo": "qux"},
            {"foo": {"foo": "bar"}},
        ],
        [
            {},
            {"foo": "qux"},
            {"foo": {"foo": "bar"}},
        ],
    ),
    (
        "$nin list of dict and list",
        {
            "foo": {"$nin": [{"bar": "baz"}, ["bar", "baz"]]},
        },
        [
            {"foo": {"bar": "baz"}},
            {"foo": ["bar", "baz"]},
            {"foo": [1, {"bar": "baz"}]},
            {"foo": [1, ["bar", "baz"]]},
            {"foo": {"bar": "qux"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz", "qux": "baz"}},
        ],
        [
            {"foo": {"bar": "qux"}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz", "qux": "baz"}},
        ],
    ),
    (
        "$nin None",
        {
            "foo": {"$nin": ["bar", None]},
        },
        [
            {"foo": None},
            {"bar": None},
            {},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": "baz"},
            {"foo": {"foo": "bar"}},
        ],
    ),
    (
        "$nin nested object path",
        {
            "foo.bar": {"$nin": ["baz", "qux"]},
        },
        [
            {"foo": {"bar": "baz"}},
            {"foo": [{"bar": "qux"}]},
            {"foo": {"bar": ["baz", "qux"]}},
            {},
            {"foo": "bar"},
            {"foo": {"bar": "baz", "qux": "baz"}},
            {"foo": {"bar": "qux", "qux": "baz"}},
        ],
        [
            {},
            {"foo": "bar"},
        ],
    ),
    (
        "indexed nested object path with intermediate arrays on doc",
        {
            "foo.1.bar": {"$nin": ["baz", "qux"]},
        },
        [
            {"foo": [{"bar": "baz"}, {"jaz": "qux"}]},
            {"foo": [{"jaz": "qux"}, {"bar": "baz"}]},
            {"foo": [{"bar": ["jaz", "baz"]}]},
            {"foo": {"1": {"bar": "baz"}, "2": {"jaz": "qux"}}},
            {"foo": [[{"bar": "baz"}, {"jaz": "qux"}]]},
        ],
        [
            {"foo": [{"bar": "baz"}, {"jaz": "qux"}]},
            {"foo": [{"bar": ["jaz", "baz"]}]},
            {"foo": [[{"bar": "baz"}, {"jaz": "qux"}]]},
        ],
    ),
    (
        "unindexed nested object path against null",
        {"foo.bar": {"$nin": ["bar", None]}},
        [
            {"foo": [{"bar": "baz"}]},
            {},
            {"foo": "bar"},
            {"foo": {"bar": None}},
        ],
        [
            {"foo": [{"bar": "baz"}]},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_nin(test_db, benchmark, name, query, input, expected):
    q = Query(query)
    assert_mongo_behavior(test_db, name, input, expected, q)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name


def test_mgqpy_nin_validation():
    with pytest.raises(TypeError):
        Query({"foo": {"$nin": "str"}}).match({})
