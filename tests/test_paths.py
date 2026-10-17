import pytest

from mgqpy import Query

from .helpers import assert_matches, get_filter_results, get_mongo_results


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


@pytest.mark.parametrize("query,documents,hits", [
    ({"x.y": None}, [{}, {"x": 1}, {"x": [1]}, {"x": [{}]}, {"x": []},
                     {"x": [[{}]]}, {"x": [None]}, {"x": [{"y": None}]}], [0, 1, 3, 7]),
    ({"x.y": {"$in": [None]}}, [{"x": 1}, {"x": [1]}, {"x": [{}]}], [0, 2]),
    ({"x.y": {"$gte": None}}, [{"x": 1}, {"x": [1]}, {"x": [{}]}], [0, 2]),
    ({"x.y": {"$lte": None}}, [{"x": 1}, {"x": [1]}, {"x": [{}]}], [0, 2]),
    ({"x.y": {"$exists": True}}, [{"x": [[{"y": 1}]]}, {"x": [1, {"y": None}]}], [1]),
    ({"x.y": 1}, [{"x": [[{"y": 1}]]}, {"x": [{"y": 1}]}], [1]),
    ({"x.0.y": 1}, [{"x": [[{"y": 1}]]}, {"x": [{"y": 1}]}], [0, 1]),
    ({"x.0": 1}, [{"x": [[1]]}, {"x": [{"0": [1]}]}, {"x": [0, {"0": 1}]}], [1, 2]),
    ({"x.0": [1]}, [{"x": [[1]]}, {"x": [{"0": [1]}]}, {"x": [1]}], [0, 1]),
    ({"x.0.y": None}, [{"x": [1]}, {"x": [{"y": 1}]}, {"x": []}], [1]),
    ({"x.0.y": {"$exists": False}}, [{"x": [1]}, {"x": [{"y": 1}]}, {"x": []}], [0, 2]),
    ({"x.9": None}, [{"x": [1]}, {"x": [{}]}], [1]),
    ({"x": 1}, [{"x": [[1]]}, {"x": [1]}, {"x": [[[1]]]}], [1]),
    ({"x": {"$gt": 0}}, [{"x": [[1]]}, {"x": [1]}], [1]),
    ({"x": {"$in": [1]}}, [{"x": [[1]]}, {"x": [1]}], [1]),
    ({"x": {"$mod": [3, 1]}}, [{"x": [[1]]}, {"x": [1]}], [1]),
    ({"x": {"$regex": "^a"}}, [{"x": [["abc"]]}, {"x": ["abc"]}], [1]),
    ({"x": {"$not": {"$gt": 10, "$lt": 0}}}, [{"x": [-1, 11]}, {"x": [3]}], [1]),
    ({"x": {"$elemMatch": {"0": 1}}}, [{"x": [[1]]}, {"x": [[{"0": 1}]]}], [0]),
    ({"x": {"$elemMatch": {"0": 1}}}, [{"x": [[[1]]]}, {"x": [[[]]]}], [0]),
    ({"x": {"$elemMatch": {"y": None}}}, [{"x": [[]]}, {"x": [None]}], [0]),
])
def test_traversal_candidates(test_db, query, documents, hits):
    expected = [documents[i] for i in hits]
    assert get_mongo_results(test_db, query, documents) == expected
    assert get_filter_results(Query(query).test, documents) == expected


@pytest.mark.parametrize("path,documents,hits", [
    ("x", [{"x": None}, {"x": []}, {"x": {}}, {"x": 0}, {}], [0, 1, 2, 3]),
    ("x.y", [{"x": {"y": None}}, {"x": 1}, {"x": None}, {},
             {"x": [{}, {"y": None}]}, {"x": [[{"y": 1}]]}, {"x": []}], [0, 4]),
    ("x.1", [{"x": [0, 1]}, {"x": [0]}, {"x": {"1": 1}},
             {"x": [{"1": 1}]}], [0, 2, 3]),
])
@pytest.mark.parametrize("operand", [True, False, "", None, 0, 1])
def test_exists_uses_the_same_paths(test_db, path, documents, hits, operand):
    if operand is False or operand is None or operand == 0:
        hits = [i for i in range(len(documents)) if i not in hits]
    assert_matches(test_db, {path: {"$exists": operand}}, documents, hits)


def test_index_first_short_circuits_and_propagates_reached_errors():
    error = RuntimeError("numeric-field lookup failed")

    class BrokenFields(dict):
        def __contains__(self, key):
            raise error

    predicate = Query({"x.0": 7})
    assert predicate.test({"x": [7, BrokenFields()]}) is True
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": [0, BrokenFields()]})
    assert caught.value is error
    # An indexed error is not converted to failure so an alternative can match.
    predicate = Query({"x.0.y": 7})
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": [BrokenFields(), {"0": {"y": 7}}]})
    assert caught.value is error
