import pytest
from mgqpy import Query
from pymongo import collection


testcases = [
    (
        "implicit $and",
        {"foo": "bar", "baz": 2},
        [
            {"foo": "bar", "baz": 2},
            {},
            {"foo": "bar"},
            {"baz": 2},
            {"foo": {"foo": "bar"}},
        ],
        [{"foo": "bar", "baz": 2}],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_and(test_db: collection.Collection, name, query, input, expected):
    q = Query(query)
    actual = filter(q.match, input)
    assert list(actual) == expected, name

    test_db.insert_many(input)
    mongo_expected = test_db.find(q._query, projection={"_id": False})
    assert list(mongo_expected) == expected, name
