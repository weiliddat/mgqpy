import pickle
import re
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

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
    {"$size": 2147483648}, {"$size": 2147483648.0}, {"$size": 2**63 - 1},
    {"$regex": "["}, {"$regex": 1}, {"$regex": "a", "$options": 1},
    {"$regex": "a\0b"},
    {"$regex": "a", "$options": "q"},
    {"$regex": re.compile("a", re.I), "$options": "m"},
    {"$in": "bad"}, {"$nin": "bad"}, {"$in": [{"$gt": 1}]},
    {"$all": {}}, {"$elemMatch": 1}, {"$gt": 1, "a": 2},
    {"$elemMatch": []}, {"$elemMatch": {"$gt": 1, "a": 2}},
    {"$elemMatch": {"a": 2, "$gt": 1}},
    {"$elemMatch": {"$not": {}}}, {"$elemMatch": {"$not": 1}},
    {"$elemMatch": {"$and": [{"$gt": 1}, {"$lt": 3}]}},
    {"$elemMatch": {"$all": [{"$elemMatch": {"$gt": 1}}, 2]}},
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
    {"x": OrderedDict([(1, 2)])},
    {"x": {"$mod": [1j, 0]}},
    {"x": {"$regex": re.compile(b"a")}},
    {"x": re.compile(b"a", re.LOCALE)},
    {"x": re.compile("a\0b")},
    {"x": {"$in": [re.compile("a\0b")]}},
    {"x": {"$regex": re.compile("a\0b")}},
    {"x": {"$regex": "(?<name>a)"}},  # PCRE spelling is outside the Python re subset.
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


@pytest.mark.parametrize("query,document,expected", [
    ({}, {}, True),
    ({"x": 1}, {"x": 1}, True),
    ({"x": 1}, {"x": 2}, False),
    ({"$or": [{"x": 1}, {"x": {"$regex": "^a", "$options": "i"}}]}, {"x": "ABC"}, True),
    ({"x": {"$not": re.compile("^a")}}, {"x": "abc"}, False),
    ({"x": {"$all": [{"$elemMatch": {"a": {"$in": [1, 2]}}}]}}, {"x": [{"a": 2}]}, True),
    ({"x": {"$elemMatch": {"$gt": 1, "$lt": 3}}}, {"x": [0, 2, 4]}, True),
    ({"x": {"$all": [re.compile("^a")]}}, {"x": ["abc"]}, True),
])
def test_pickle_round_trip(query, document, expected):
    predicate = Query(query)
    query.clear()
    restored = pickle.loads(pickle.dumps(predicate))
    assert restored.test(document) is expected


def test_predicate_can_be_submitted_to_a_process_pool():
    predicate = Query({"x": {"$in": [1, 2]}})
    with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
        assert list(pool.map(predicate.test, [{"x": 1}, {"x": 3}])) == [True, False]


@pytest.mark.parametrize("query,location", [
    ({"items": {"$elemMatch": {"x": {"$typo": 1}}}}, "query.items.$elemMatch.x"),
    ({"items": {"$all": [{"$elemMatch": {"x": 1}}, {"$elemMatch": {"x": {"$typo": 1}}}]}},
     "query.items.$all[1].$elemMatch.x"),
    ({"items": {"$not": {"$elemMatch": {"x": {"$typo": 1}}}}}, "query.items.$not.$elemMatch.x"),
    ({"$or": [{}, {"items": {"$elemMatch": {"$and": [{"x": {"$typo": 1}}]}}}]},
     "query.$or[1].items.$elemMatch.$and[0].x"),
    ({"items": {"$elemMatch": {"$typo": 1}}}, "query.items.$elemMatch"),
    ({"items": {"$elemMatch": {"$elemMatch": {"$typo": 1}}}},
     "query.items.$elemMatch.$elemMatch"),
    ({"items": {"$all": [{"$elemMatch": {"$typo": 1}}]}}, "query.items.$all[0].$elemMatch"),
])
def test_invalid_nested_query_names_its_location(query, location):
    with pytest.raises(InvalidQuery) as caught:
        Query(query)
    assert str(caught.value) == f"{location}: unknown operator: $typo"


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


@pytest.mark.parametrize("container", [dict, OrderedDict])
def test_literal_containers_are_deep_copied(container):
    value = container(nested=([2],))
    predicate = Query({"x": {"$eq": value}})
    value["nested"][0].append(3)
    assert predicate.test({"x": container(nested=([2],))}) is True
    assert predicate.test({"x": value}) is False


@pytest.mark.parametrize("mode", ["field", "value-elemMatch", "singleton-all"])
def test_regex_preparation_preserves_aliased_literal_values(test_db, mode):
    regex = {"$regex": "^a", "$options": "i"}
    expression, value = regex, "ABC"
    if mode == "value-elemMatch":
        expression, value = {"$elemMatch": regex}, ["ABC"]
    elif mode == "singleton-all":
        expression, value = {"$all": [{"$elemMatch": regex}]}, ["ABC"]
    query = {"literal": {"$eq": regex}, "pattern": expression}
    document = {"literal": regex, "pattern": value}
    test_db.insert_one(document.copy())
    assert test_db.count_documents(query) == 1
    assert Query(query).test(document) is True


@pytest.mark.parametrize("doc", [None, [], 1, "x"])
def test_document_must_be_a_dict(doc):
    with pytest.raises(TypeError):
        Query({}).test(doc)
