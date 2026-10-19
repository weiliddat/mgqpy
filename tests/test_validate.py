import re
import sys
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

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


@pytest.mark.parametrize("container", [dict, OrderedDict])
def test_literal_containers_are_deep_copied(container):
    value = container(nested=([2],))
    predicate = Query({"x": {"$eq": value}})
    value["nested"][0].append(3)
    assert predicate.test({"x": container(nested=([2],))}) is True
    assert predicate.test({"x": value}) is False


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
def test_reached_container_comparison_errors_propagate(op, operand, doc):
    expression = {op: operand}
    for query in (
        {"x": expression},
        {"x": {"$not": expression}},
        {"$nor": [{"x": expression}]},
        {"$or": [{"x": expression}, {}]},
    ):
        with pytest.raises(TypeError):
            Query(query).test({"x": doc})


@pytest.mark.parametrize("op,deciding_value,result", [
    ("$and", False, False), ("$or", True, True), ("$nor", True, False),
])
def test_logical_operators_stop_once_decided(op, deciding_value, result):
    bad = {"x": {"$gt": {"a": 1}}}
    predicate = Query({op: [{"ok": True}, bad]})
    assert predicate.test({"ok": deciding_value, "x": {"a": "z"}}) is result
    with pytest.raises(TypeError):
        predicate.test({"ok": not deciding_value, "x": {"a": "z"}})


def test_implicit_and_and_operator_conjunction_stop_once_decided():
    doc = {"x": {"a": "z"}}
    assert Query({"ok": True, "x": {"$gt": {"a": 1}}}).test(doc) is False
    assert Query({"x": {"$eq": None, "$gt": {"a": 1}}}).test(doc) is False
    with pytest.raises(TypeError):
        Query({"x": {"$gt": {"a": 1}}, "ok": True}).test(doc)


class BrokenTail(list):
    """A document array whose tail raises the supplied exception."""

    def __init__(self, prefix, error):
        super().__init__(prefix)
        self.error = error

    def __iter__(self):
        yield from super().__iter__()
        raise self.error


@pytest.mark.parametrize("expression,value,result", [
    (7, 7, True), ({"$ne": 7}, 7, False),
    ({"$gt": 6}, 7, True), ({"$gte": 7}, 7, True),
    ({"$lt": 8}, 7, True), ({"$lte": 7}, 7, True),
    ({"$in": [7]}, 7, True), ({"$nin": [7]}, 7, False),
    ({"$not": {"$eq": 7}}, 7, False),
    ({"$mod": [3, 1]}, 7, True), ({"$regex": "^a"}, "abc", True),
])
@pytest.mark.parametrize("dotted", [False, True])
def test_arrays_stop_at_a_decisive_element(expression, value, result, dotted):
    key, prefix = ("x.y", {"y": value}) if dotted else ("x", value)
    predicate = Query({key: expression})
    error = RuntimeError("unreadable tail")
    assert predicate.test({"x": BrokenTail([prefix], error)}) is result
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": BrokenTail([], error)})
    assert caught.value is error


@pytest.mark.parametrize("expression,value", [
    ({"$size": 2}, [1, 2]), ({"$all": [7]}, [7]),
    ({"$elemMatch": {"a": 7}}, [{"a": 7}]), ({"$exists": True}, None),
])
def test_array_operators_stop_at_a_decisive_subdocument(expression, value):
    predicate = Query({"x.y": expression})
    error = RuntimeError("unreadable tail")
    assert predicate.test({"x": BrokenTail([{"y": value}], error)}) is True
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": BrokenTail([], error)})
    assert caught.value is error


def test_membership_operands_stop_once_decided():
    nan = Decimal("sNaN")
    assert Query({"x": {"$in": [1, nan]}}).test({"x": 1}) is True
    assert Query({"x": {"$all": [1, nan]}}).test({"x": [0]}) is False
    for query, doc in (
        ({"x": {"$in": [nan, 1]}}, {"x": 1}),
        ({"x": {"$all": [nan, 1]}}, {"x": [0]}),
        ({"x": {"$gt": 0}}, {"x": Decimal("NaN")}),
    ):
        with pytest.raises(InvalidOperation):
            Query(query).test(doc)


def test_deep_document_recursion_error_propagates():
    value = 0
    for _ in range(sys.getrecursionlimit()):
        value = [value]
    with pytest.raises(RecursionError):
        Query({"x": 1}).test({"x": value})
