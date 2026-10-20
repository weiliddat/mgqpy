import pytest

from mgqpy import InvalidQuery, Query

from .helpers import assert_matches


@pytest.mark.parametrize("query,hits", [
    ({"x": 1, "y": 2}, [0]),
    ({"$and": [{"x": 1}, {"y": 2}]}, [0]),
    ({"$or": [{"x": 1}, {"y": 2}]}, [0, 1, 2]),
    ({"$nor": [{"x": 1}, {"y": 2}]}, [3, 4]),
    ({"$and": [{"x": 1}, {"$or": [{"y": 2}, {"y": 3}]}]}, [0, 1]),
    ({"$or": [{"x": 1, "y": 2}, {"$and": [{"x": 3}, {"y": 2}]}]}, [0, 2]),
    ({"$nor": [{"$and": [{"x": 1}, {"y": 2}]}, {"x": 3}]}, [1, 3, 4]),
    ({"x": {"$not": {"$eq": 1}}}, [2, 3, 4]),
    ({"x": {"$not": {"$in": [1, 3], "$ne": 4}}}, [3, 4]),
])
def test_logical_queries(test_db, query, hits):
    assert_matches(test_db, query, [{"x": 1, "y": 2}, {"x": 1, "y": 3},
                                   {"x": 3, "y": 2}, {"x": 4}, {}], hits)


@pytest.mark.parametrize("expression,hits", [
    ({"$elemMatch": {"$not": {"$gt": 1}}}, [0, 2]),
    ({"$not": {"$elemMatch": {"$gt": 1}}}, [2, 3, 4, 5]),
])
def test_inner_and_outer_elem_match_negation(test_db, expression, hits):
    assert_matches(test_db, {"x": expression},
                   [{"x": [0, 2]}, {"x": [2]}, {"x": [[2]]}, {"x": []}, {}, {"x": 2}], hits)


class BrokenNumber(int):
    error = RuntimeError("comparison failed")

    def __eq__(self, other):
        raise self.error

    __gt__ = __ge__ = __lt__ = __le__ = __eq__


@pytest.mark.parametrize("op", ["$gt", "$gte", "$lt", "$lte"])
@pytest.mark.parametrize("value,operand", [(BrokenNumber(1), 0),
                                           ({"a": BrokenNumber(1)}, {"a": 0}),
                                           ([BrokenNumber(1)], [0])])
def test_reached_comparison_error_keeps_its_identity(op, value, operand):
    expression = {op: operand}
    for query in ({"x": expression}, {"x": {"$not": expression}},
                  {"$nor": [{"x": expression}]}, {"$or": [{"x": expression}, {}]}):
        with pytest.raises(RuntimeError) as caught:
            Query(query).test({"x": value})
        assert caught.value is BrokenNumber.error


@pytest.mark.parametrize("op,deciding_value,result", [
    ("$and", False, False), ("$or", True, True), ("$nor", True, False),
])
def test_logical_short_circuit(op, deciding_value, result):
    predicate = Query({op: [{"ok": True}, {"x": {"$gt": 0}}]})
    assert predicate.test({"ok": deciding_value, "x": BrokenNumber(1)}) is result
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"ok": not deciding_value, "x": BrokenNumber(1)})
    assert caught.value is BrokenNumber.error


def test_implicit_and_and_operator_conjunction_short_circuit():
    doc = {"x": BrokenNumber(1)}
    assert Query({"ok": True, "x": {"$gt": 0}}).test(doc) is False
    assert Query({"x": {"$eq": None, "$gt": 0}}).test(doc) is False
    with pytest.raises(RuntimeError) as caught:
        Query({"x": {"$gt": 0}, "ok": True}).test(doc)
    assert caught.value is BrokenNumber.error


class BrokenTail(list):
    def __init__(self, prefix, error):
        super().__init__(prefix)
        self.error = error

    def __iter__(self):
        yield from super().__iter__()
        raise self.error


def test_empty_all_does_not_traverse_but_keeps_validation_and_operator_order():
    error = RuntimeError("unreadable tail")
    doc = {"x": BrokenTail([{"y": []}], error)}
    for query, expected in (
        ({"x.y": {"$all": []}}, False),
        ({"x.y": {"$not": {"$all": []}}}, True),
        ({"$nor": [{"x.y": {"$all": []}}]}, True),
    ):
        assert Query(query).test(doc) is expected
    # $gt precedes $all in operator order, regardless of insertion order.
    with pytest.raises(RuntimeError) as caught:
        Query({"x.y": {"$all": [], "$gt": 0}}).test(doc)
    assert caught.value is error
    with pytest.raises(InvalidQuery):
        Query({"x.y": {"$all": [], "$size": -1}})


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


@pytest.mark.parametrize("expression,value", [
    ({"$eq": 7}, 7), ({"$all": [7]}, 7),
    ({"$not": {"$eq": 7}}, 0), ({"$elemMatch": {"$eq": 7}}, [7]),
])
def test_value_elem_match_stops_before_an_unread_tail(expression, value):
    error = RuntimeError("unreadable tail")
    predicate = Query({"x": {"$elemMatch": expression}})
    assert predicate.test({"x": BrokenTail([value], error)}) is True
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": BrokenTail([], error)})
    assert caught.value is error


@pytest.mark.parametrize("expression,deciding", [({"$eq": 7}, 7), ({"$not": {"$eq": 7}}, 0)])
def test_value_elem_match_preserves_reached_comparison_errors(expression, deciding):
    predicate = Query({"x": {"$elemMatch": expression}})
    assert predicate.test({"x": [deciding, BrokenNumber(9)]}) is True
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": [BrokenNumber(9), deciding]})
    assert caught.value is BrokenNumber.error


def test_membership_operands_short_circuit():
    bad = BrokenNumber(9)
    assert Query({"x": {"$in": [1, bad]}}).test({"x": 1}) is True
    assert Query({"x": {"$all": [0, bad]}}).test({"x": [1]}) is False
    for query, doc in (({"x": {"$in": [bad, 1]}}, {"x": 1}),
                       ({"x": {"$all": [bad, 0]}}, {"x": [1]})):
        with pytest.raises(RuntimeError) as caught:
            Query(query).test(doc)
        assert caught.value is BrokenNumber.error


def test_all_replays_reached_values_without_reading_an_unneeded_tail():
    error = RuntimeError("unreadable tail")
    predicate = Query({"x.y": {"$all": [2, 1]}})
    assert predicate.test({"x": BrokenTail([{"y": [1]}, {"y": [2]}], error)}) is True
    with pytest.raises(RuntimeError) as caught:
        predicate.test({"x": BrokenTail([{"y": [2]}], error)})
    assert caught.value is error
    assert predicate.test({"x": [{"y": [2]}]}) is False


def test_unclassified_comparison_error_is_not_a_type_mismatch():
    error = RuntimeError("custom comparison failed")

    class Broken:
        def __eq__(self, other):
            raise error

        __gt__ = __ge__ = __lt__ = __le__ = __eq__

    for op in ("$eq", "$gt", "$gte", "$lt", "$lte"):
        for value, operand in ((Broken(), 1), ({"a": Broken()}, {"a": 1}),
                               ([Broken()], [1])):
            with pytest.raises(RuntimeError) as caught:
                Query({"x": {op: operand}}).test({"x": value})
            assert caught.value is error


@pytest.mark.parametrize("value,operand", [({"a": 1, "b": BrokenNumber(9)}, {"a": 0, "b": 0}),
                                          ([1, BrokenNumber(9)], [0, 0])])
def test_container_comparison_stops_at_a_decisive_prefix(value, operand):
    assert Query({"x": {"$eq": operand}}).test({"x": value}) is False
    assert Query({"x": {"$gt": operand}}).test({"x": value}) is True


def test_reached_lookup_error_propagates_under_negation():
    error = RecursionError("failed lookup")

    class BrokenDocument(dict):
        def __contains__(self, key):
            raise error

    for query in ({"x": 1}, {"x": {"$not": {"$eq": 1}}}, {"$nor": [{"x": 1}]}):
        with pytest.raises(RecursionError) as caught:
            Query(query).test(BrokenDocument())
        assert caught.value is error


def test_successful_evaluation_returns_a_bool():
    class TruthyNumber(int):
        def __eq__(self, other):
            return [True]

        __gt__ = __ge__ = __lt__ = __le__ = __eq__

    for op in ("$eq", "$gt", "$gte", "$lt", "$lte"):
        assert Query({"x": {op: 0}}).test({"x": TruthyNumber(1)}) is True


@pytest.mark.parametrize("op,key,expected", [
    ("$gt", "z", True), ("$gt", "a", False),
    ("$gte", "z", True), ("$gte", "a", False),
    ("$lt", "a", True), ("$lt", "z", False),
    ("$lte", "a", True), ("$lte", "z", False),
])
def test_dict_key_comparison_normalizes_truth_and_propagates_errors(op, key, expected):
    error = RuntimeError("truth conversion failed")

    class Verdict:
        def __bool__(self):
            raise error

    class Key(str):
        fail = False

        def __gt__(self, other):
            return Verdict() if self.fail else [True] if super().__gt__(other) else []

        def __lt__(self, other):
            return Verdict() if self.fail else [True] if super().__lt__(other) else []

    field = {"x": {op: {"m": 0}}}
    doc = {"x": {Key(key): 0}}
    for query in (field, {"$and": [field]}, {"$or": [field]}):
        assert Query(query).test(doc) is expected
        Key.fail = True
        with pytest.raises(RuntimeError) as caught:
            Query(query).test(doc)
        assert caught.value is error
        Key.fail = False


@pytest.mark.parametrize("side", ["query", "document"])
def test_dict_key_equality_uses_the_keys_own_inequality(side):
    class FoldKey(str):
        def __eq__(self, other):
            return self.casefold() == str(other).casefold()

        __hash__ = str.__hash__

    error = RuntimeError("key comparison failed")

    class RaisingKey(str):
        def __ne__(self, other):
            raise error

        __hash__ = str.__hash__

    def pair(key):
        special = {key: 1}
        return (special, {"a": 1}) if side == "query" else ({"a": 1}, special)

    # str's inherited != decides, not the case-folding ==.
    operand, value = pair(FoldKey("A"))
    assert Query({"x": {"$eq": operand}}).test({"x": value}) is False
    assert Query({"x": {"$ne": operand}}).test({"x": value}) is True
    operand, value = pair(FoldKey("a"))
    assert Query({"x": {"$eq": operand}}).test({"x": value}) is True
    operand, value = pair(RaisingKey("a"))
    for op in ("$eq", "$ne"):
        with pytest.raises(RuntimeError) as caught:
            Query({"x": {op: operand}}).test({"x": value})
        assert caught.value is error
