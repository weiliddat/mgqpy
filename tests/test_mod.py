import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$mod",
        {
            "foo": {"$mod": [3, 0]},
        },
        [
            {"foo": -3},
            {"foo": 0},
            {"foo": 1},
            {"foo": 2},
            {"foo": 3},
            {"foo": 4},
            {"foo": 5},
            {"foo": 6},
            {"foo": "6"},
        ],
        [
            {"foo": -3},
            {"foo": 0},
            {"foo": 3},
            {"foo": 6},
        ],
    ),
    (
        "$mod with floats",
        {
            "foo": {"$mod": [3.5, 0.1]},
        },
        [
            {"foo": 2.9},
            {"foo": 3.0},
            {"foo": 3.1},
            {"foo": 3.5},
            {"foo": 3.9},
            {"foo": 4},
            {"foo": 5},
        ],
        [
            {"foo": 3.0},
            {"foo": 3.1},
            {"foo": 3.5},
            {"foo": 3.9},
        ],
    ),
    (
        "$mod with negative input",
        {
            "foo": {"$mod": [-3, -0]},
        },
        [
            {"foo": -3},
            {"foo": 0},
            {"foo": 1},
            {"foo": 2},
            {"foo": 3},
            {"foo": 4},
            {"foo": 5},
            {"foo": 6},
        ],
        [
            {"foo": -3},
            {"foo": 0},
            {"foo": 3},
            {"foo": 6},
        ],
    ),
    (
        "$mod with dict access",
        {
            "foo.bar": {"$mod": [3, 0]},
        },
        [
            {"foo": {"bar": -3}},
        ],
        [
            {"foo": {"bar": -3}},
        ],
    ),
    (
        "$mod against list",
        {
            "foo": {"$mod": [3, 0]},
        },
        [
            {"foo": [3]},
            {"foo": [3, 6]},
            {"foo": [3, 1]},
        ],
        [
            {"foo": [3]},
            {"foo": [3, 6]},
            {"foo": [3, 1]},
        ],
    ),
    (
        "$mod with indexed list",
        {
            "foo.1": {"$mod": [3, 1]},
        },
        [
            {"foo": [3, 6]},
            {"foo": [3, 1]},
        ],
        [
            {"foo": [3, 1]},
        ],
    ),
    (
        "$mod with implicit list access",
        {
            "foo.bar": {"$mod": [3, 1]},
        },
        [
            {"foo": None},
            {"foo": []},
            {"foo": [{"bar": 6}]},
            {"foo": [{"bar": 1}]},
        ],
        [
            {"foo": [{"bar": 1}]},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_mod(test_db, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = get_filter_results(q.test, input)
    assert actual == expected, name


@pytest.mark.parametrize("operands,values,expected", [
    ([3, -1], [-4, -1.5, -0.5, 4, True], [-4, -1.5]),
    ([-3.5, 1.9], [-4, -1.5, 1.9, 4, False], [1.9, 4]),
    ([3, 0], [float("nan"), float("inf"), -float("inf"), True, 3], [3]),
    ([7, 1], [2**60, 2**60 + 1, -(2**60)], [2**60]),
    ([1, 0], [float(2**63), 1e30, -float(2**63), -(2**63), 2**63 - 1],
     [-float(2**63), -(2**63), 2**63 - 1]),
])
def test_signed_mod_and_numeric_boundaries(test_db, operands, values, expected):
    query = {"x": {"$mod": operands}}
    documents = [{"x": value} for value in values]
    expected = [{"x": value} for value in expected]
    assert get_mongo_results(test_db, query, documents) == expected
    assert get_filter_results(Query(query).test, documents) == expected
