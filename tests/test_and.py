import pytest
from mgqpy import Query


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
def test_mgqpy_and(name, query, input, expected):
    q = Query(query)
    actual = filter(q.match, input)
    assert list(actual) == expected, name
