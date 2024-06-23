import re
import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$regex",
        {
            "foo": {
                "$regex": "^ba",
            },
        },
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
        ],
    ),
    (
        "$regex with i flag",
        {
            "foo": {
                "$regex": "^ba",
                "$options": "i",
            },
        },
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
        ],
    ),
    (
        "$regex with s flag",
        {
            "foo": {
                "$regex": "bar.baz",
                "$options": "s",
            },
        },
        [
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
        [
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
    ),
    (
        "$regex with m flag",
        {
            "foo": {
                "$regex": "^baz",
                "$options": "m",
            },
        },
        [
            {"foo": "baz"},
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
        [
            {"foo": "baz"},
            {"foo": "bar\nbaz"},
        ],
    ),
    (
        "$regex with x flag",
        {
            "foo": {
                "$regex": "^ baz $",
                "$options": "x",
            },
        },
        [
            {"foo": "baz"},
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
        [
            {"foo": "baz"},
        ],
    ),
    (
        "$regex with nested dict/lists",
        {"foo.bar": {"$regex": "^baz"}},
        [
            {"foo": [{"bar": "bazo"}]},
            {"foo": {"bar": ["bazi"]}},
            {"foo": {"bar": ["qux", "bazqux"]}},
            {"foo": ["bar", "baz"]},
            {"foo": None},
            {},
        ],
        [
            {"foo": [{"bar": "bazo"}]},
            {"foo": {"bar": ["bazi"]}},
            {"foo": {"bar": ["qux", "bazqux"]}},
        ],
    ),
    (
        "$regex with indexed lists",
        {"foo.0.bar": {"$regex": "^baz"}},
        [
            {"foo": [{"bar": "bazo"}]},
            {"foo": {"bar": ["bazi"]}},
            {"foo": {"bar": ["qux", "bazqux"]}},
            {"foo": ["bar", "baz"]},
            {"foo": None},
            {},
        ],
        [
            {"foo": [{"bar": "bazo"}]},
        ],
    ),
    (
        "implicit $regex",
        {"foo": re.compile("^ba", re.IGNORECASE)},
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
        ],
    ),
    (
        "$in with implicit $regex",
        {
            "foo": {
                "$in": [
                    re.compile("^ba", re.IGNORECASE),
                    re.compile("^qu", re.IGNORECASE),
                ]
            }
        },
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_or(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name
