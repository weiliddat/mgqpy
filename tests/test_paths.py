import pytest

from mgqpy import Query

from .helpers import get_filter_results, get_mongo_results


@pytest.mark.parametrize("expression,value", [
    ({"$eq": 2}, 2), ({"$gt": 1}, 2), ({"$gte": 2}, 2),
    ({"$lt": 3}, 2), ({"$lte": 2}, 2), ({"$in": [2]}, 2),
    ({"$mod": [3, 2]}, 2), ({"$regex": "^a"}, "abc"),
    ({"$size": 2}, [2, 3]), ({"$all": [2, 3]}, [2, 3]),
    ({"$elemMatch": {"a": 2}}, [{"a": 2}]), ({"$exists": True}, 2),
])
@pytest.mark.parametrize("segment", ["0", "00", "²", "٠"])
def test_canonical_ascii_array_indices(test_db, expression, value, segment):
    documents = [
        {"x": [{"value": value}]},
        {"x": {segment: {"value": value}}},
        {"x": []},
        {},
    ]
    expected = documents[:2] if segment == "0" else documents[1:2]
    query = {f"x.{segment}.value": expression}
    assert get_mongo_results(test_db, query, documents) == expected
    assert get_filter_results(Query(query).test, documents) == expected
