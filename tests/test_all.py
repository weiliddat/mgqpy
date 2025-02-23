import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$all",
        {
            "foo": {"$all": ["bar", "baz"]},
        },
        [
            {"foo": ["bar", "baz"]},
            {"foo": [["bar", "baz"]]},
            {"foo": ["qux", "bar", "baz"]},
            {"foo": ["qux", ["bar", "baz"]]},
            {"foo": "bar"},
            {"foo": ["baz"]},
            {"foo": None},
            {},
        ],
        [
            {"foo": ["bar", "baz"]},
            {"foo": ["qux", "bar", "baz"]},
        ],
    ),
    (
        "$all with nested list ov",
        {
            "foo": {"$all": [["baz", "qux"]]},
        },
        [
            {"foo": ["baz", "qux"]},
            {"foo": [["baz", "qux"]]},
            {"foo": [["quux", "quuz"], ["baz", "qux"]]},
            {"foo": [1, 2, ["baz", "qux"], "quux"]},
            {"foo": ["baz"]},
            {"foo": None},
            {},
        ],
        [
            {"foo": ["baz", "qux"]},
            {"foo": [["baz", "qux"]]},
            {"foo": [["quux", "quuz"], ["baz", "qux"]]},
            {"foo": [1, 2, ["baz", "qux"], "quux"]},
        ],
    ),
    (
        "$all with dict access",
        {
            "foo.bar": {"$all": ["baz", "qux"]},
        },
        [
            {"foo": {"bar": ["baz", "qux"]}},
            {"foo": [{"bar": ["baz"]}, {"bar": ["baz", "qux"]}]},
            {"foo": {"bar": [["baz", "qux"]]}},
            {"foo": {"bar": ["quux", "baz", "qux"]}},
            {"foo": {"bar": [["quux", "quuz"], ["baz", "qux"]]}},
            {"foo": {"bar": [1, 2, ["baz", "qux"], "quux"]}},
            {"foo": {"bar": "baz"}},
            {"foo": {"bar": None}},
            {},
        ],
        [
            {"foo": {"bar": ["baz", "qux"]}},
            {"foo": [{"bar": ["baz"]}, {"bar": ["baz", "qux"]}]},
            {"foo": {"bar": ["quux", "baz", "qux"]}},
        ],
    ),
    (
        "$all with indexed array access",
        {
            "foo.1.bar": {"$all": ["baz", "qux"]},
        },
        [
            {"foo": [{"bar": ["baz", "qux"]}]},
            {"foo": [{"bar": ["baz"]}, {"bar": ["baz", "qux"]}]},
            {"foo": [{"bar": [["baz", "qux"]]}]},
            {"foo": [1, {"bar": ["quux", "baz", "qux"]}]},
            {"foo": [{"bar": [["quux", "quuz"], ["baz", "qux"]]}]},
            {"foo": [{"bar": [1, 2, ["baz", "qux"], "quux"]}]},
            {"foo": {"bar": "baz"}},
            {"foo": {"bar": None}},
            {},
        ],
        [
            {"foo": [{"bar": ["baz"]}, {"bar": ["baz", "qux"]}]},
            {"foo": [1, {"bar": ["quux", "baz", "qux"]}]},
        ],
    ),
    (
        "$all with $elemMatch subqueries",
        {
            "qty": {
                "$all": [
                    {"$elemMatch": {"size": "M", "num": {"$gt": 50}}},
                    {"$elemMatch": {"num": 100, "color": "green"}},
                ]
            }
        },
        [
            {
                "code": "xyz",
                "tags": ["school", "book", "bag", "headphone", "appliance"],
                "qty": [
                    {"size": "S", "num": 10, "color": "blue"},
                    {"size": "M", "num": 45, "color": "blue"},
                    {"size": "L", "num": 100, "color": "green"},
                ],
            },
            {
                "code": "abc",
                "tags": ["appliance", "school", "book"],
                "qty": [
                    {"size": "6", "num": 100, "color": "green"},
                    {"size": "6", "num": 50, "color": "blue"},
                    {"size": "8", "num": 100, "color": "brown"},
                ],
            },
            {
                "code": "efg",
                "tags": ["school", "book"],
                "qty": [
                    {"size": "S", "num": 10, "color": "blue"},
                    {"size": "M", "num": 100, "color": "blue"},
                    {"size": "L", "num": 100, "color": "green"},
                ],
            },
            {
                "code": "ijk",
                "tags": ["electronics", "school"],
                "qty": [{"size": "M", "num": 100, "color": "green"}],
            },
        ],
        [
            {
                "code": "efg",
                "tags": ["school", "book"],
                "qty": [
                    {"size": "S", "num": 10, "color": "blue"},
                    {"size": "M", "num": 100, "color": "blue"},
                    {"size": "L", "num": 100, "color": "green"},
                ],
            },
            {
                "code": "ijk",
                "tags": ["electronics", "school"],
                "qty": [{"size": "M", "num": 100, "color": "green"}],
            },
        ],
    ),
    (
        "$and with other $ subquery",
        {
            "foo": {
                "$all": [
                    {"$or": [{"bar": "baz"}, {"bar": "qux"}]},
                ]
            }
        },
        [
            {"foo": [{"bar": "baz"}, {"bar": "qux"}]},
            {"foo": [{"bar": {"$eq": "baz"}}, {"bar": {"$eq": "qux"}}]},
        ],
        [],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_all(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.test, input)
    assert actual == expected, name


def test_mgqpy_invalid_query():
    query = {"foo": {"$all": {"bar": "baz"}}}
    q = Query(query)
    assert q.test({"foo": "bar"}) is False

    query = {"foo": {"$all": [{"$elemMatch": {"bar": "baz"}}]}}
