import re

import pytest
from pymongo.errors import OperationFailure

from mgqpy import InvalidQuery, Query


@pytest.mark.parametrize("op", ["$and", "$or", "$nor"])
@pytest.mark.parametrize("children", [[], None, {}, "bad", [1], [None], [{}, []], [{}, {"$or": []}]])
def test_invalid_logical_children(test_db, op, children):
    query = {op: children}
    with pytest.raises(InvalidQuery):
        Query(query)
    with pytest.raises(OperationFailure):
        list(test_db.find(query))


INVALID_EXPRESSIONS = [
    {"$options": "i"},
    {"$not": 1}, {"$not": None}, {"$not": {}}, {"$not": []}, {"$not": {"a": 1}},
    {"$mod": "bad"}, {"$mod": []}, {"$mod": [1]}, {"$mod": [1, 2, 3]},
    {"$mod": ["1", 0]}, {"$mod": [True, 0]}, {"$mod": [1, False]},
    {"$mod": [0, 0]}, {"$mod": [0.5, 0]}, {"$mod": [-0.5, 0]},
    {"$mod": [float("inf"), 0]}, {"$mod": [1, float("nan")]},
    {"$mod": [float(2**63), 0]}, {"$mod": [1, 1e30]},
    {"$size": -1}, {"$size": 1.5}, {"$size": float("nan")},
    {"$size": float("inf")}, {"$size": True}, {"$size": "2"},
    {"$regex": "["}, {"$regex": 1}, {"$regex": "a", "$options": 1},
    {"$regex": "a", "$options": "q"},
    {"$regex": re.compile("a", re.I), "$options": "m"},
    {"$in": "bad"}, {"$nin": "bad"}, {"$in": [{"$gt": 1}]},
    {"$all": {}}, {"$elemMatch": 1}, {"$gt": 1, "a": 2},
    *[{op: re.compile("a")} for op in ("$ne", "$gt", "$gte", "$lt", "$lte")],
    {"$all": [1, {"$elemMatch": {"a": 1}}]},
    {"$typo": 1},
]


@pytest.mark.parametrize("expression", INVALID_EXPRESSIONS)
def test_invalid_expressions_cannot_be_negated_into_matches(test_db, expression):
    queries = [
        {"x": expression},
        {"x": {"$not": expression}},
        {"$nor": [{"x": expression}]},
    ]
    for query in queries:
        with pytest.raises(InvalidQuery):
            Query(query)
        with pytest.raises(OperationFailure):
            list(test_db.find(query))


@pytest.mark.parametrize("query", [
    None, [], "bad", {1: 2}, {"x": {1: 2}},
    {"x": {"$eq": {1: 2}}}, {"x": {"$in": [{1: 2}]}},
    {"x": {"$mod": [1j, 0]}},
    {"x": {"$regex": re.compile(b"a")}},
    {"x": re.compile(b"a", re.LOCALE)},
    {"x": {"$regex": "(?<name>a)"}},  # PCRE spelling is outside the Python re subset.
    {"x": {"$elemMatch": {"$gt": 1}}},
    {"x": {"$all": [{"$or": [{"a": 1}]}]}},
    {"x": {"$all": [{"$elemMatch": {"a": 1}}, 2]}},
    {"$where": "this.x"}, {"x": {"$type": "string"}},
    {"$or": [{}, {"x": {"$type": "string"}}]},
    {"x": {"$not": {"$type": "string"}}},
    {"x": {"$elemMatch": {"a": {"$type": "string"}}}},
    {"x": {"$all": [{"$elemMatch": {"a": {"$type": "string"}}}]}},
])
def test_invalid_python_queries_and_unsupported_features(query):
    with pytest.raises(InvalidQuery):
        Query(query)


@pytest.mark.parametrize("query", [
    {}, {"x": "a"}, {"x": {}}, {"x": {"a": 1, "$other": 2}},
    {"$and": [{"x": 1}]}, {"$or": [{"x": 1}]}, {"$nor": [{"x": 1}]},
    {"x": {"$size": 2.0}}, {"x": {"$size": 0}},
    {"x": {"$all": []}}, {"x": {"$in": []}}, {"x": {"$nin": []}},
    {"x": {"$elemMatch": {}}},
    {"x": {"$all": [{"$elemMatch": {"a": 1}}]}},
    {"x": {"$not": re.compile("a")}},
])
def test_valid_construction(query):
    assert type(Query(query).test({})) is bool


def test_query_owns_a_deep_snapshot():
    values = [1, {"nested": [2]}]
    regex = {"$regex": "^a", "$options": "i"}
    query = {"$and": [{"x": {"$in": values}}, {"name": regex}, {"name": regex}]}
    predicate = Query(query)
    assert regex == {"$regex": "^a", "$options": "i"}
    values[1]["nested"].append(3)
    values[0] = 9
    query["$and"][1]["name"]["$regex"] = "["
    assert predicate.test({"x": 1, "name": "ABC"}) is True
    assert predicate.test({"x": {"nested": [2]}, "name": "abc"}) is True
    assert predicate.test({"x": 9, "name": "abc"}) is False
    assert not hasattr(predicate, "validate")


def test_regex_preparation_preserves_aliased_literal_values(test_db):
    regex = {"$regex": "^a", "$options": "i"}
    query = {"literal": {"$eq": regex}, "pattern": regex}
    document = {"literal": regex, "pattern": "ABC"}
    test_db.insert_one(document.copy())
    assert test_db.count_documents(query) == 1
    assert Query(query).test(document) is True


@pytest.mark.parametrize("doc", [None, [], 1, "x"])
def test_document_must_be_a_dict(doc):
    with pytest.raises(TypeError):
        Query({}).test(doc)


@pytest.mark.parametrize("op", ["$gt", "$gte", "$lt", "$lte"])
@pytest.mark.parametrize("operand,doc", [({"a": 1}, {"a": "z"}), ([1], ["z"])])
def test_incomparable_containers_are_interim_non_matches(op, operand, doc):
    expression = {op: operand}
    assert Query({"x": expression}).test({"x": doc}) is False
    assert Query({"x": {"$not": expression}}).test({"x": doc}) is False
    assert Query({"$nor": [{"x": expression}]}).test({"x": doc}) is False
