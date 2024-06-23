import copy

import pytest

from mgqpy import Query

testcases = [
    (
        "$in list of str",
        {
            "foo": {"$in": ["bar", "baz"]},
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
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": ["qux", "baz"]},
        ],
    ),
    (
        "$in list of dict and list",
        {
            "foo": {"$in": [{"bar": "baz"}, ["bar", "baz"]]},
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
            {"foo": {"bar": "baz"}},
            {"foo": ["bar", "baz"]},
            {"foo": [1, {"bar": "baz"}]},
            {"foo": [1, ["bar", "baz"]]},
        ],
    ),
    (
        "$in None",
        {
            "foo": {"$in": ["bar", None]},
        },
        [
            {"foo": None},
            {"bar": None},
            {},
            {"foo": "bar"},
            {"foo": {"foo": "bar"}},
        ],
        [
            {"foo": None},
            {"bar": None},
            {},
            {"foo": "bar"},
        ],
    ),
    (
        "$in nested object path",
        {
            "foo.bar": {"$in": ["baz", "qux"]},
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
            {"foo": {"bar": "baz"}},
            {"foo": [{"bar": "qux"}]},
            {"foo": {"bar": ["baz", "qux"]}},
            {"foo": {"bar": "baz", "qux": "baz"}},
            {"foo": {"bar": "qux", "qux": "baz"}},
        ],
    ),
    (
        "indexed nested object path with intermediate arrays on doc",
        {
            "foo.1.bar": {"$in": ["baz", "qux"]},
        },
        [
            {"foo": [{"bar": "baz"}, {"jaz": "qux"}]},
            {"foo": [{"jaz": "qux"}, {"bar": "baz"}]},
            {"foo": [{"bar": ["jaz", "baz"]}]},
            {"foo": {"1": {"bar": "baz"}, "2": {"jaz": "qux"}}},
            {"foo": [[{"bar": "baz"}, {"jaz": "qux"}]]},
        ],
        [
            {"foo": [{"jaz": "qux"}, {"bar": "baz"}]},
            {"foo": {"1": {"bar": "baz"}, "2": {"jaz": "qux"}}},
        ],
    ),
    (
        "unindexed nested object path against null",
        {"foo.bar": {"$in": ["bar", None]}},
        [
            {"foo": [{"bar": "baz"}]},
            {},
            {"foo": "bar"},
            {"foo": {"bar": None}},
            {"foo": [{"bar": "qux"}]},
        ],
        [{}, {"foo": "bar"}, {"foo": {"bar": None}}],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_in(test_db, name, query, input, expected):
    q = Query(query)

    test_db.insert_many(copy.deepcopy(input))
    mongo_expected = test_db.find(q._query, projection={"_id": False})
    assert list(mongo_expected) == expected, name

    actual = filter(q.match, input)
    assert list(actual) == expected, name


def test_mgqpy_in_validation():
    with pytest.raises(TypeError):
        Query({"foo": {"$in": "str"}}).match({})
