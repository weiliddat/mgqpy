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
def test_mgqpy_mod(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name


def test_mgqpy_in_validation():
    with pytest.raises(ValueError):
        Query({"foo": {"$mod": [1]}}).match({})
    with pytest.raises(ValueError):
        Query({"foo": {"$mod": []}}).match({})
    with pytest.raises(ValueError):
        Query({"foo": {"$mod": [1, 2, 3]}}).match({})
