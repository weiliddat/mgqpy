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


@pytest.mark.parametrize("path,expression,documents,hits", [
    ("", 5, [{"": 5}, {"": [5]}, {"": {"": 5}}, {"x": 5}, {}], [0, 1]),
    (".", 5, [{"": [5]}, {"": {"": 5}}, {"": [{"": 5}]}, {"": 5}, {}], [0, 1]),
    ("x.", None, [{"x": [None]}, {"x": [{}]}, {"x": [{"": None}]},
                  {"x": []}, {"x": {"": None}}, {}, {"x": 1}], [0, 4, 5, 6]),
    ("x.", 5, [{"x": [5]}, {"x": [{"": 5}]}, {"x": {"": 5}},
               {"x": {"": [5]}}, {"x": [[5]]}, {"x": 5}], [0, 2, 3]),
    ("x..", 5, [{"x": {"": [5]}}, {"x": [{"": [5]}]}, {"x": [5]},
                {"x": {"": {"": 5}}}, {"x": [[5]]}], [0, 1, 3]),
    ("x...", 5, [{"x": {"": {"": [5]}}}, {"x": [{"": {"": [5]}}]},
                 {"x": {"": [5]}}, {"x": [5]}], [0, 1]),
    ("x..y", 5, [{"x": {"": {"y": 5}}}, {"x": [{"": {"y": 5}}]},
                 {"x": [{"y": 5}]}, {"x": [[{"": {"y": 5}}]]}], [0, 1]),
    ("x.0.", 5, [{"x": [[5]]}, {"x": [5]}, {"x": [{"": 5}]},
                  {"x": {"0": {"": 5}}}], [0, 2, 3]),
    ("x.0..", 5, [{"x": [{"": [5]}]}, {"x": [[5]]}, {"x": [{"": 5}]}], [0]),
    ("x.", {"$exists": True}, [{"x": []}, {"x": [None]}, {"x": {}},
                               {"x": {"": None}}, {"x": 5}, {}], [0, 1, 3]),
    ("x.", {"$exists": False}, [{"x": []}, {"x": {}}, {"x": 5}, {}], [1, 2, 3]),
    ("x.", {"$size": 1}, [{"x": [5]}, {"x": [{}]}, {"x": [[5]]}, {"x": []}], [0, 1, 2]),
    ("x.0.", {"$size": 1}, [{"x": [[5]]}, {"x": [5]}, {"x": [[5, 6]]}], [0]),
    ("x.0..", {"$size": 1}, [{"x": [{"": [5]}]}, {"x": [[5]]}], [0]),
    ("x.", {"$all": [1, 2]}, [{"x": [1, 2]}, {"x": [[1, 2]]},
                              {"x": [{"": [1, 2]}]}], [0]),
    ("x.", {"$elemMatch": {"$gt": 1}}, [{"x": [2]}, {"x": [[2]]}, {"x": [0]}], [0]),
    ("x.0.", {"$size": 0}, [{"x": [[[]]]}, {"x": [[0]]}, {"x": [[]]},
                            {"x": [[[[]]]]}, {"x": {"0": [[]]}},
                            {"x": [[[0]], {"0": {"": []}}]},
                            {"x": [[[0]], {"0": {"": [[]]}}]}], [0, 2, 5]),
    ("x.0.", {"$not": {"$size": 0}}, [{"x": [[[]]]}, {"x": [[0]]}, {"x": [[]]},
                                      {"x": [[[[]]]]}], [1, 3]),
    ("x.0.", {"$size": 1}, [{"x": [[[]]]}, {"x": [[0]]}, {"x": [[1, 2]]},
                            {"x": [[[1, 2]]]}], [0, 1, 3]),
    ("x.0.", {"$elemMatch": {"$eq": 1}}, [{"x": [[[1]]]}, {"x": [[1]]},
                                        {"x": [[[[1]]]]}, {"x": [[0]]}], [0, 1]),
    ("x.0.", {"$elemMatch": {"a": 1}}, [{"x": [[[{"a": 1}]]]}, {"x": [[{"a": 1}]]},
                                      {"x": [[[[{"a": 1}]]]]}, {"x": [[{"a": 0}]]}], [0, 1]),
    ("x.0.", {"$all": [{"$elemMatch": {"$eq": 1}}]},
     [{"x": [[[1]]]}, {"x": [[1]]}, {"x": [[[[1]]]]}], [0, 1]),
    ("x.0.", {"$all": [{"$elemMatch": {"$eq": 1}}, {"$elemMatch": {"$eq": 2}}]},
     [{"x": [[[1], [2]]]}, {"x": [[[1, 2]]]}, {"x": [[1, 2]]},
      {"x": [[[1], [0]]]}, {"x": [[[[1], [2]]]]}], [0, 1, 2]),
    ("x.0.", 1, [{"x": [[[1]]]}, {"x": [[1]]}, {"x": [[[[1]]]]}], [1]),
    ("x.0.", {"$all": [1]}, [{"x": [[[1]]]}, {"x": [[1]]}, {"x": [[[[1]]]]}], [1]),
    ("x.", {"$size": 0}, [{"x": [[[]]]}, {"x": [[]]}, {"x": []}], [2]),
    ("x.0", {"$size": 0}, [{"x": [[[]]]}, {"x": [[]]}, {"x": []}], [1]),
])
def test_empty_path_components(test_db, path, expression, documents, hits):
    assert_matches(test_db, {path: expression}, documents, hits)


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

    # The indexed empty-suffix candidate stream is also lazy, not flattened.
    predicate = Query({"x.0.": {"$elemMatch": {"a": 1}}})
    assert predicate.test({"x": [[[{"a": 1}], [BrokenFields()]]]}) is True
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": [[[BrokenFields()], [{"a": 1}]]]})
    assert caught.value is error


def test_path_subclasses_split_independently_of_equal_strings():
    class First(str):
        def split(self, *args):
            return ["first"]

    class Second(str):
        def split(self, *args):
            return ["second"]

    doc = {"first": 1, "second": 2, "p": 3}
    for _ in range(2):
        assert Query({"p": 3}).test(doc) is True
        assert Query({First("p"): 1}).test(doc) is True
        assert Query({Second("p"): 2}).test(doc) is True
