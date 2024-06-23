import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results

testcases = [
    (
        "$elemMatch",
        {
            "foo": {
                "$elemMatch": {
                    "bar": {"$gt": 10},
                    "baz": {"$lt": 100},
                }
            }
        },
        [
            {"foo": [{"bar": 20, "baz": 90}, {"bar": 0, "baz": 200}]},
            {"foo": [{"bar": 10, "baz": 100}, {"bar": 20, "baz": 90}]},
            {"foo": [{"bar": 20, "baz": 100}, {"bar": 10, "baz": 90}]},
            {"foo": [{"bar": 20}, {"baz": 90}]},
            {"foo": [{}]},
            {"foo": []},
            {"foo": None},
        ],
        [
            {"foo": [{"bar": 20, "baz": 90}, {"bar": 0, "baz": 200}]},
            {"foo": [{"bar": 10, "baz": 100}, {"bar": 20, "baz": 90}]},
        ],
    ),
    (
        "$elemMatch dict access",
        {"foo.bar": {"$elemMatch": {"a": "b", "c": "d"}}},
        [
            {"foo": {"bar": [{"a": "z", "c": "d"}, {"a": "b", "c": "z"}]}},
            {"foo": {"bar": [{}, 2, {"g": "f", "a": "b", "c": "d"}]}},
            {
                "foo": [
                    {"bar": {}},
                    {"bar": [{"a": "z", "c": "d"}, {"a": "b", "c": "d"}]},
                ]
            },
            {"foo": {"bar": [{"c": "d"}, {"a": "b"}]}},
            {"foo": {}},
        ],
        [
            {"foo": {"bar": [{}, 2, {"g": "f", "a": "b", "c": "d"}]}},
            {
                "foo": [
                    {"bar": {}},
                    {"bar": [{"a": "z", "c": "d"}, {"a": "b", "c": "d"}]},
                ]
            },
        ],
    ),
    (
        "$elemMatch list access",
        {"foo.0.bar": {"$elemMatch": {"a": "b", "c": "d"}}},
        [
            {
                "foo": [
                    {"bar": [{"z": "b", "d": "d"}]},
                    {"bar": [{"a": "b", "c": "d"}]},
                ]
            },
            {
                "foo": [
                    {"bar": [{"a": "b", "c": "d"}]},
                    {"bar": [{"z": "b", "d": "d"}]},
                ]
            },
            {"foo": [{"bar": [{}, 2, {"g": "f", "a": "b", "c": "d"}]}]},
            {"foo": [{"bar": [{"c": "d"}, {"a": "b"}]}]},
        ],
        [
            {
                "foo": [
                    {"bar": [{"a": "b", "c": "d"}]},
                    {"bar": [{"z": "b", "d": "d"}]},
                ]
            },
            {"foo": [{"bar": [{}, 2, {"g": "f", "a": "b", "c": "d"}]}]},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_elem_match(test_db, benchmark, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = benchmark(get_filter_results, q.match, input)
    assert actual == expected, name
