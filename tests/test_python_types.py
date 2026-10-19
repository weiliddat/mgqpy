"""Additional tests for python-native types that require coercion.

These tests cover:
* datetime.date ↔︎ ISO-8601 strings
* decimal.Decimal ↔︎ numbers / numeric strings
* uuid.UUID ↔︎ strings

The document structures mimic the shape that would result from
`pydantic.BaseModel.model_dump()` without importing pydantic here – the
library should work with plain dict / list inputs provided by the user.
"""

import datetime as _dt
import decimal as _dec
import uuid as _uuid

import pytest

from mgqpy import Query

from .helpers import get_mongo_results, get_filter_results


@pytest.mark.parametrize("operand,cast", [(72, float), (72.0, int)])
@pytest.mark.parametrize("op,expected", [
    ("$gt", ["above", "last"]),
    ("$gte", ["equal", "above", "last"]),
    ("$lt", ["below", "last"]),
    ("$lte", ["below", "equal", "last"]),
])
def test_mixed_numeric_ranges(test_db, operand, cast, op, expected):
    miss, hit = (0, 73) if op in ("$gt", "$gte") else (99, 71)
    documents = [
        {"case": "below", "x": cast(71)},
        {"case": "equal", "x": cast(72)},
        {"case": "above", "x": cast(73)},
        {"case": "last", "x": [cast(miss)] * 99 + [cast(hit)]},
        {"case": "miss", "x": [cast(miss)] * 100},
    ]
    query = {"x": {op: operand}}
    assert [d["case"] for d in get_mongo_results(test_db, query, documents)] == expected
    assert [d["case"] for d in get_filter_results(Query(query).test, documents)] == expected


@pytest.mark.parametrize("op,above,below", [
    ("$gt", True, False), ("$gte", True, False),
    ("$lt", False, True), ("$lte", False, True),
])
def test_mixed_numeric_ranges_preserve_integer_precision(test_db, op, above, below):
    for operand, value, expected in (
        (float(2**53), 2**53 + 1, above),
        (2**53 + 1, float(2**53), below),
    ):
        query, document = {"x": {op: operand}}, {"x": value}
        # Each query needs its own fixture collection contents.
        test_db.delete_many({})
        assert bool(get_mongo_results(test_db, query, [document])) is expected
        assert Query(query).test(document) is expected


@pytest.mark.parametrize(
    "doc, query, expected",
    [
        (
            {"ts": _dt.datetime(2025, 7, 31, 12, 0, 0)},
            {"ts": {"$eq": "2025-07-31T12:00:00"}},
            True,
        ),
        (
            {"ts": _dt.datetime(2025, 7, 31, 0, 0, 0)},
            {"ts": {"$eq": "2025-07-31"}},
            True,
        ),
        (
            {"ts": _dt.datetime(2025, 7, 31, 12, 0, 0)},
            {"ts": {"$gt": "2025-07-31"}},
            True,
        ),
        (
            {"ts": _dt.datetime(2025, 7, 31, 12, 0, 0)},
            {"ts": {"$gt": "2025-07-30T23:59:59"}},
            True,
        ),
        (
            {"ts": "2025-07-31T12:00:00"},
            {"ts": {"$lt": _dt.datetime(2025, 8, 1)}},
            True,
        ),
        (
            {"ts": "asdf"},
            {"ts": {"$eq": _dt.datetime(2025, 8, 1)}},
            False,
        ),
    ],
)
def test_datetime_coercion(doc, query, expected):
    assert Query(query).test(doc) is expected


def test_datetime_with_timezone():
    aware = _dt.datetime(2025, 7, 31, 10, 0, 0, tzinfo=_dt.timezone.utc)

    assert Query({"ts": {"$eq": "2025-07-31T10:00:00+00:00"}}).test({"ts": aware})
    assert Query({"ts": {"$eq": aware}}).test({"ts": "2025-07-31T10:00:00+00:00"})
    assert Query({"ts": {"$gt": "2025-07-31"}}).test({"ts": aware})
    assert Query({"ts": {"$eq": "2025-07-31T10:00:00"}}).test({"ts": aware})


@pytest.fixture()
def fruit_basket_dict():
    """Dictionary shaped like the output of a dumped Pydantic model."""

    return {
        "fruits": [
            {"type": "berry", "harvested": _dt.date(2024, 8, 1)},
            {"type": "aggregate", "harvested": _dt.date(2024, 8, 2)},
            {"type": "hybrid", "harvested": "2024-08-03"},
        ]
    }


@pytest.mark.parametrize(
    "query, expected",
    [
        (
            {"fruits.0.harvested": {"$eq": "2024-08-01"}},
            True,
        ),
        (
            {"fruits.0.harvested": {"$eq": _dt.date(2024, 8, 1)}},
            True,
        ),
        (
            {"fruits.1.type": {"$eq": "aggregate"}},
            True,
        ),
        (
            {"fruits.harvested": {"$in": ["2024-08-02"]}},
            True,
        ),
        (
            {"fruits.0.harvested": {"$gt": "2024-07-31"}},
            True,
        ),
        (
            {"fruits.0.harvested": {"$lt": "2024-08-02"}},
            True,
        ),
        (
            {"fruits.2.harvested": {"$eq": _dt.date(2024, 8, 3)}},
            True,
        ),
    ],
)
def test_date_coercion(fruit_basket_dict, query, expected):
    assert Query(query).test(fruit_basket_dict) is expected


@pytest.mark.parametrize(
    "doc, query, expected",
    [
        (
            {"x": _dec.Decimal("3.14")},
            {"x": {"$eq": "3.14"}},
            True,
        ),
        (
            {"x": "2.71"},
            {"x": {"$eq": _dec.Decimal("2.71")}},
            True,
        ),
        (
            {"x": _dec.Decimal("10")},
            {"x": {"$gt": "9"}},
            True,
        ),
        (
            {"x": _dec.Decimal("10")},
            {"x": {"$gt": _dec.Decimal("9")}},
            True,
        ),
        (
            {"x": _dec.Decimal("10")},
            {"x": {"$gt": "a"}},
            False,
        ),
    ],
)
def test_decimal_coercion(doc, query, expected):
    assert Query(query).test(doc) is expected


@pytest.mark.parametrize(
    "doc, query, expected",
    [
        (
            {"u": _uuid.UUID("0123456789abcdef0123456789abcdef")},
            {"u": {"$eq": "0123456789abcdef0123456789abcdef"}},
            True,
        ),
        (
            {"u": "0123456789abcdef0123456789abcdef"},
            {"u": {"$eq": _uuid.UUID("0123456789abcdef0123456789abcdef")}},
            True,
        ),
        (
            {"u": ["123", None, _uuid.uuid1(), "0123456789abcdef0123456789abcdef"]},
            {"u": {"$eq": _uuid.UUID("0123456789abcdef0123456789abcdef")}},
            True,
        ),
    ],
)
def test_uuid_coercion(doc, query, expected):
    assert Query(query).test(doc) is expected
