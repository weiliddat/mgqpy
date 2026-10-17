"""Intentional Python extensions, with explicit BSON server reference values."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from bson import Binary, Decimal128
import pytest

from mgqpy import Query


UID = UUID("0123456789abcdef0123456789abcdef")
EAST = timezone(timedelta(hours=2))


@pytest.mark.parametrize("a,b,bson_a,bson_b,order", [
    (date(2024, 8, 1), "2024-08-01", datetime(2024, 8, 1), "2024-08-01", 1),
    (datetime(2024, 8, 1, 12), "2024-08-01T12:00:00",
     datetime(2024, 8, 1, 12), "2024-08-01T12:00:00", 1),
    (datetime(2024, 8, 1, 12, tzinfo=EAST), "2024-08-01T12:00:00",
     datetime(2024, 8, 1, 10), "2024-08-01T12:00:00", 1),
    (datetime(2024, 8, 1, 12, tzinfo=EAST), "2024-08-01T10:00:00+00:00",
     datetime(2024, 8, 1, 10), "2024-08-01T10:00:00+00:00", 1),
    (Decimal("10"), "10", Decimal128("10"), "10", -1),
    # Decimal(str(float)), intentionally not Mongo's exact binary-float ordering.
    (Decimal("0.1"), 0.1, Decimal128("0.1"), 0.1, -1),
    (UID, UID.hex, Binary.from_uuid(UID), UID.hex, 1),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("shape", ["scalar", "document", "array"])
def test_pairwise_conversion_and_server_difference(test_db, a, b, bson_a, bson_b, order, reverse, shape):
    if reverse:
        a, b, bson_a, bson_b, order = b, a, bson_b, bson_a, -order
    if shape == "document":
        a, b, bson_a, bson_b = ({"a": [v]} for v in (a, b, bson_a, bson_b))
    elif shape == "array":
        a, b, bson_a, bson_b = ([{"a": v}] for v in (a, b, bson_a, bson_b))
    # Terminal index prevents implicit leaf-array matching in both engines.
    test_db.insert_one({"x": [bson_a]})
    for op, orders in (("$eq", [0]), ("$gt", [1]), ("$gte", [0, 1]),
                       ("$lt", [-1]), ("$lte", [-1, 0])):
        assert Query({"x.0": {op: b}}).test({"x": [a]}) is (0 in orders)
        # Mongo never converts strings. Its scalar type brackets reject these
        # pairs, except Decimal128/double, which are already numeric BSON values.
        bracketed = shape == "scalar" and (isinstance(bson_a, str) or isinstance(bson_b, str))
        expected = False if bracketed else order in orders
        assert bool(test_db.count_documents({"x.0": {op: bson_b}})) is expected


@pytest.mark.parametrize("native,text", [(date(2024, 8, 1), "2024-08-01"),
                                         (Decimal("3.14"), "3.14"), (UID, str(UID))])
def test_equality_consumers_share_recursive_conversion(native, text):
    literal = {"a": [text]}
    doc = {"x": {"a": [native]}}
    for expression, expected in ((literal, True), ({"$eq": literal}, True),
                                  ({"$in": [literal]}, True), ({"$all": [literal]}, True),
                                  ({"$ne": literal}, False), ({"$nin": [literal]}, False),
                                  ({"$not": {"$eq": literal}}, False)):
        assert Query({"x": expression}).test(doc) is expected
    assert Query({"x": {"$elemMatch": {"a": [text]}}}).test({"x": [{"a": [native]}]}) is True
    # A scalar-only prefix must not disable conversion in a later array value.
    assert Query({"x": {"$all": [text, "last"]}}).test({"x": ["other"] * 160 + [native, "last"]}) is True


@pytest.mark.parametrize("value,operand,expected", [
    (datetime(2025, 7, 31, 12), "2025-07-31", True),
    ("2025-07-31T12:00:00", datetime(2025, 8, 1), False),
    (date(2024, 8, 2), "2024-08-01", True),
    (Decimal("10"), "9", True), (Decimal("10"), Decimal("9"), True),
    (Decimal("10"), "a", False), (UID, "invalid-uuid", False),
])
def test_native_ranges(value, operand, expected):
    assert Query({"x": {"$gt": operand}}).test({"x": value}) is expected


@pytest.mark.parametrize("value,operand", [(date(2024, 8, 1), "invalid-date"),
                                          (Decimal("1"), "bad"), (UID, "bad"),
                                          (Decimal("1"), True)])
def test_failed_conversion_is_not_equality(value, operand):
    assert Query({"x": operand}).test({"x": value}) is False
    assert Query({"x": value}).test({"x": operand}) is False


@pytest.mark.parametrize("nan", [Decimal("NaN"), Decimal("sNaN")])
@pytest.mark.parametrize("op,orders", [("$eq", [0]), ("$gt", [1]), ("$gte", [0, 1]),
                                      ("$lt", [-1]), ("$lte", [-1, 0])])
def test_decimal_nan_rules_against_bson(test_db, nan, op, orders):
    test_db.insert_one({"x": Decimal128(nan)})
    assert Query({"x": {op: float("nan")}}).test({"x": nan}) is (0 in orders)
    assert bool(test_db.count_documents({"x": {op: float("nan")}})) is (0 in orders)
    assert Query({"x": {op: 0}}).test({"x": nan}) is False
    assert bool(test_db.count_documents({"x": {op: 0}})) is False
    test_db.delete_many({})
    test_db.insert_one({"x": [Decimal128(nan)]})
    assert Query({"x": {op: [-float("inf")]}}).test({"x": [nan]}) is (-1 in orders)
    assert bool(test_db.count_documents({"x": {op: [-float("inf")]}})) is (-1 in orders)


def test_naive_and_aware_datetimes_are_not_silently_aligned():
    value = datetime(2024, 8, 2, tzinfo=timezone.utc)
    predicate = Query({"$or": [{"ok": True}, {"x": {"$gt": datetime(2024, 8, 1)}}]})
    assert predicate.test({"ok": True, "x": value}) is True
    with pytest.raises(TypeError):
        predicate.test({"ok": False, "x": value})


def test_conversions_are_pairwise_not_global_normalization():
    native = datetime(2024, 8, 1, 12, tzinfo=EAST)
    naive = "2024-08-01T12:00:00"
    utc = "2024-08-01T10:00:00+00:00"
    assert Query({"x": naive}).test({"x": native}) is True
    assert Query({"x": utc}).test({"x": native}) is True
    assert Query({"x": utc}).test({"x": naive}) is False
    # Effective converted types precede field names in document ordering too.
    assert Query({"x": {"$gt": {"z": "2024-08-01"}}}).test({"x": {"a": date(2024, 9, 1)}}) is False


class Wrapped:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == getattr(other, "value", other)

    def __lt__(self, other):
        return self.value < getattr(other, "value", other)

    def __gt__(self, other):
        return self.value > getattr(other, "value", other)

    def __le__(self, other):
        return self.value <= getattr(other, "value", other)

    def __ge__(self, other):
        return self.value >= getattr(other, "value", other)


class Child(Wrapped):
    pass


@pytest.mark.parametrize("value,operand,order", [
    (Wrapped(1), 1, 0), (Child(2), Wrapped(1), 1), (Wrapped(0), Child(1), -1),
])
@pytest.mark.parametrize("shape", ["scalar", "document", "array"])
def test_unclassified_values_keep_python_comparisons(value, operand, order, shape):
    if shape == "document":
        value, operand = {"a": value}, {"a": operand}
    elif shape == "array":
        value, operand = [value], [operand]
    for a, b, sign in ((value, operand, order), (operand, value, -order)):
        for op, orders in (("$eq", [0]), ("$ne", [-1, 1]), ("$gt", [1]),
                           ("$gte", [0, 1]), ("$lt", [-1]), ("$lte", [-1, 0])):
            assert Query({"x.0": {op: b}}).test({"x": [a]}) is (sign in orders)
