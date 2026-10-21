"""$type follows the BSON type PyMongo encodes, with mgqpy's native brackets."""

import datetime
import enum
import re
from decimal import Decimal
from fractions import Fraction
from uuid import UUID

import pytest

from mgqpy import Query

from .helpers import assert_matches

DOCUMENTS = [
    {"x": "a"}, {"x": 1}, {"x": 2**31}, {"x": 1.5}, {"x": None}, {},
    {"x": [1, "a"]}, {"x": [[1]]}, {"x": []}, {"x": {"a": 1}}, {"x": [{"a": 1}]},
    {"x": True}, {"x": datetime.datetime(2024, 1, 1)}, {"x": re.compile("a")},
    {"x": b"ab"}, {"x": [None]}, {"x": -2**31 - 1}, {"x": 2**63 - 1},
]
SHAPED = [{"x": "507f1f77bcf86cd799439011"}, {"x": "12345678-1234-5678-1234-567812345678"},
          {"x": "12345678123456781234567812345678"}, {"x": "2024-08-01"},
          {"x": "2024-08-01T00:00:00+00:00"}]
NESTED = [{"x": [{}, {"a": None}]}, {"x": [{}]}, {"x": [{"a": [1]}]}, {"x": {"a": 1}}]


@pytest.mark.parametrize("query,documents,hits", [
    ({"x": {"$type": "string"}}, DOCUMENTS, [0, 6]),
    ({"x": {"$type": "int"}}, DOCUMENTS, [1, 6]),
    ({"x": {"$type": "long"}}, DOCUMENTS, [2, 16, 17]),
    ({"x": {"$type": "double"}}, DOCUMENTS, [3]),
    ({"x": {"$type": "number"}}, DOCUMENTS, [1, 2, 3, 6, 16, 17]),
    ({"x": {"$type": "null"}}, DOCUMENTS, [4, 15]),
    ({"x": {"$type": "array"}}, DOCUMENTS, [6, 7, 8, 10, 15]),
    ({"x": {"$type": "object"}}, DOCUMENTS, [9, 10]),
    ({"x": {"$type": "bool"}}, DOCUMENTS, [11]),
    ({"x": {"$type": "date"}}, DOCUMENTS, [12]),
    ({"x": {"$type": "regex"}}, DOCUMENTS, [13]),
    ({"x": {"$type": "binData"}}, DOCUMENTS, [14]),
    ({"x": {"$type": "objectId"}}, DOCUMENTS, []),
    ({"x": {"$type": 2.0}}, DOCUMENTS, [0, 6]),
    ({"x": {"$type": 18}}, DOCUMENTS, [2, 16, 17]),
    ({"x": {"$type": ["string", 16]}}, DOCUMENTS, [0, 1, 6]),
    ({"x": {"$not": {"$type": "number"}}}, DOCUMENTS, [0, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
    # A terminal index does not expand the array it selects.
    ({"x.0": {"$type": "array"}}, DOCUMENTS, [7]),
    ({"x.0": {"$type": "int"}}, DOCUMENTS, [6]),
    ({"x": {"$elemMatch": {"$type": "int"}}}, DOCUMENTS, [6]),
    # Missing members are not null, and values reached through arrays expand once.
    ({"x.a": {"$type": "null"}}, NESTED, [0]),
    ({"x.a": {"$type": "array"}}, NESTED, [2]),
    ({"x.a": {"$type": "int"}}, NESTED, [2, 3]),
    # Strings are never typed by their content.
    *[({"x": {"$type": alias}}, SHAPED, hits) for alias, hits in (
        ("string", [0, 1, 2, 3, 4]), ("objectId", []), ("binData", []), ("date", []),
        ("timestamp", []))],
    # Document-form $elemMatch, with nested logical operators and $not.
    ({"x": {"$elemMatch": {"$and": [
        {"a": {"$type": "int"}},
        {"$or": [{"b": {"$type": "string"}}, {"b": {"$not": {"$type": "number"}}}]},
    ]}}}, [{"x": [{"a": 1, "b": "s"}]}, {"x": [{"a": 1, "b": None}]}, {"x": [{"a": 1, "b": 2}]},
           {"x": [{"a": 1}, {"b": "s"}]}, {"x": [{"a": "1", "b": "s"}]},
           {"x": [{"a": [1], "b": "s"}]}], [0, 1, 3, 5]),
    # Value-form $elemMatch under $or and $and, with $not.
    ({"$or": [{"x": {"$elemMatch": {"$not": {"$type": "number"}}}},
              {"y": {"$elemMatch": {"$type": "string"}}}]},
     [{"x": [1, 2]}, {"x": [1, "a"]}, {"x": [1], "y": ["s"]}, {"x": [], "y": [1]},
      {"x": [None]}, {"x": 1}], [1, 2, 4]),
    ({"$and": [{"x": {"$elemMatch": {"$type": "int"}}}, {"x": {"$elemMatch": {"$type": "string"}}}]},
     [{"x": [1, "a"]}, {"x": [1]}, {"x": ["a"]}, {"x": [1.5, "a"]}], [0]),
])
def test_type_against_server(test_db, query, documents, hits):
    assert_matches(test_db, query, documents, hits)


class Level(enum.IntEnum):
    LOW = 1


@pytest.mark.parametrize("value,types", [
    # Native values use the bracket that equality and ranges already give them.
    (Decimal(1), {"decimal", "number"}),
    (Decimal("NaN"), {"decimal", "number"}),
    (bytearray(b"a"), {"binData"}),
    (UUID(int=1), {"binData"}),
    (datetime.date(2024, 1, 1), {"date"}),
    (Level.LOW, {"int", "number"}),
    (-2**63, {"long", "number"}),
    # Values PyMongo cannot encode, or encodes only by conversion, have no type.
    (2**63, set()), (Fraction(1, 2), set()), ((1,), set()), (object(), set()),
])
def test_python_values(value, types):
    matched = {alias for alias in ("decimal", "number", "binData", "date", "int", "long",
                                   "double", "array", "object", "string")
               if Query({"x": {"$type": alias}}).test({"x": value})}
    assert matched == types
