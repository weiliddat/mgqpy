"""Deferred questions, not promises of parity: https://github.com/weiliddat/mgqpy/issues/14.

Strict xfails notice a resolved difference. Only the known local failure is
allowed to xfail; a changed MongoDB result or unexpected error must fail normally.
Performance costs stay in benchmarks, not timing assertions here.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pickle
import subprocess
import sys
from uuid import UUID

from bson import Binary, Decimal128
from bson.errors import InvalidDocument
import pytest

from mgqpy import InvalidQuery, Query


class MongoDifference(AssertionError):
    """Only a local result differing from the independently checked oracle."""


UNSUPPORTED = pytest.mark.xfail(
    strict=True, raises=InvalidQuery, reason="#14: Python re subset / unsupported operator",
)
DIFFERENT = pytest.mark.xfail(
    strict=True, raises=MongoDifference, reason="#14: documented matching difference",
)


@pytest.mark.parametrize("query,document,expected", [
    pytest.param({"x": {"$regex": "(?<name>a)"}}, {"x": "a"}, True,
                 marks=UNSUPPORTED, id="pcre-named-group"),
    pytest.param({"x": {"$regex": r"\Qa.b\E"}}, {"x": "a.b"}, True,
                 marks=UNSUPPORTED, id="pcre-quoted-literal"),
    pytest.param({"x": {"$regex": r"^\p{L}+$"}}, {"x": "é"}, True,
                 marks=UNSUPPORTED, id="pcre-unicode-property"),
    pytest.param({"x": {"$regex": r"a\Kb"}}, {"x": "ab"}, True,
                 marks=UNSUPPORTED, id="pcre-match-reset"),
    pytest.param({"x": {"$regex": "^é$", "$options": "i"}}, {"x": "É"}, True,
                 marks=DIFFERENT, id="non-ascii-case-folding"),
    pytest.param({"x": {"$elemMatch": {"$gt": 1, "$lt": 3}}}, {"x": [0, 2, 4]}, True,
                 marks=UNSUPPORTED, id="value-elem-match"),
    pytest.param({"x": {"$type": "string"}}, {"x": "a"}, True,
                 marks=UNSUPPORTED, id="type-operator"),
    pytest.param({"x.": None}, {"x": [None]}, True,
                 marks=DIFFERENT, id="trailing-empty-path"),
    pytest.param({"x": datetime(2024, 8, 1, microsecond=100)},
                 {"x": datetime(2024, 8, 1, microsecond=900)}, True,
                 marks=DIFFERENT, id="sub-millisecond-datetime"),
    pytest.param({"x": datetime(2024, 8, 1)},
                 {"x": datetime(2024, 8, 1, tzinfo=timezone.utc)}, True,
                 marks=DIFFERENT, id="naive-aware-equality"),
    pytest.param({"x": {"$gt": datetime(2024, 8, 1)}},
                 {"x": datetime(2024, 8, 2, tzinfo=timezone.utc)}, True,
                 marks=pytest.mark.xfail(strict=True, raises=TypeError,
                                         reason="#14: Python naive/aware ordering"),
                 id="naive-aware-range"),
])
def test_mongodb_matching_difference(test_db, query, document, expected):
    test_db.insert_one(dict(document))
    assert bool(test_db.count_documents(query, maxTimeMS=2000)) is expected
    actual = Query(query).test(document)
    if actual is not expected:
        raise MongoDifference(f"mgqpy={actual}, MongoDB={expected}")


@DIFFERENT
@pytest.mark.parametrize("query,value,bson_value,expected", [
    pytest.param({"x": 0.1}, Decimal("0.1"), Decimal128("0.1"), False,
                 id="decimal-double-equality"),
    pytest.param({"x": {"$lt": 0.1}}, Decimal("0.1"), Decimal128("0.1"), True,
                 id="decimal-double-order"),
    pytest.param({"x": "10"}, Decimal("10"), Decimal128("10"), False,
                 id="decimal-string"),
    pytest.param({"x": "2024-08-01"}, date(2024, 8, 1), datetime(2024, 8, 1), False,
                 id="date-string"),
    pytest.param({"x": "2024-08-01T12:00:00"},
                 datetime(2024, 8, 1, 12, tzinfo=timezone(timedelta(hours=2))),
                 datetime(2024, 8, 1, 10, tzinfo=timezone.utc), False,
                 id="datetime-string-inherits-paired-zone"),
    pytest.param({"x": "0123456789abcdef0123456789abcdef"},
                 UUID("0123456789abcdef0123456789abcdef"),
                 Binary.from_uuid(UUID("0123456789abcdef0123456789abcdef")), False,
                 id="uuid-string"),
])
def test_native_conversion_difference(test_db, query, value, bson_value, expected):
    # Explicit reference values: PyMongo does not encode native Decimal or date,
    # and UUID encoding depends on the client's configured representation.
    test_db.insert_one({"x": bson_value})
    assert bool(test_db.count_documents(query, maxTimeMS=2000)) is expected
    actual = Query(query).test({"x": value})
    if actual is not expected:
        raise MongoDifference(f"mgqpy={actual}, MongoDB={expected}")


@pytest.mark.xfail(strict=True, raises=MongoDifference, reason="#14: NUL query keys accepted")
@pytest.mark.parametrize("query", [{"x\0": 1}, {"x": {"a\0": 1}}], ids=["path", "literal"])
def test_nul_keys_rejected_like_bson(test_db, query):
    # Neither query nor document can reach MongoDB: BSON keys are cstrings.
    with pytest.raises(InvalidDocument):
        test_db.insert_one(dict(query))
    with pytest.raises(InvalidDocument):
        test_db.count_documents(query)
    try:
        Query(query)
    except InvalidQuery:
        return
    raise MongoDifference("mgqpy accepted a query BSON cannot encode")


@pytest.mark.xfail(strict=True, raises=subprocess.TimeoutExpired,
                   reason="#14: Python re has no matching budget")
def test_adversarial_regex_finishes_within_budget(test_db):
    query = {"x": {"$regex": "(a+)+$"}}
    test_db.insert_one({"x": "a" * 32 + "!"})
    assert test_db.count_documents(query, maxTimeMS=2000) == 0
    # Never execute the adversarial match in pytest's process. run() kills and
    # waits for the child on timeout. Import/compilation errors are NOT xfailed.
    result = subprocess.run(
        [sys.executable, "-c",
         'from mgqpy import Query; '
         'print(Query({"x": {"$regex": "(a+)+$"}}).test({"x": "a" * 32 + "!"}))'],
        capture_output=True, text=True, timeout=2, check=True,
    )
    assert result.stdout == "False\n"


# Generated with pickle.dumps(Query({"x": 1}), protocol=4) using actual 0.9.0
# source, not a hand-built instance. v1-base emits identical bytes for this case.
# Source: https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d
LEGACY_QUERY = (
    b'\x80\x04\x95,\x00\x00\x00\x00\x00\x00\x00\x8c\x05mgqpy\x94\x8c\x05Query\x94'
    b'\x93\x94)\x81\x94}\x94\x8c\x06_query\x94}\x94\x8c\x01x\x94K\x01ssb.'
)


@pytest.mark.xfail(strict=True, raises=AttributeError, reason="#14: no cross-release pickle contract")
def test_legacy_pickle_still_evaluates():
    restored = pickle.loads(LEGACY_QUERY)
    assert restored.test({"x": 1}) is True
    assert restored.test({"x": 2}) is False


class TaggedQuery(Query):
    def __init__(self, query, tag):
        super().__init__(query)
        self.tag = tag


@pytest.mark.xfail(strict=True, raises=TypeError, reason="#14: subclass requires another constructor argument")
def test_subclass_pickle_preserves_query_and_constructor_state():
    restored = pickle.loads(pickle.dumps(TaggedQuery({"x": 1}, "tag")))
    assert restored.tag == "tag"
    assert restored.test({"x": 1}) is True
    assert restored.test({"x": 2}) is False


@pytest.mark.xfail(strict=True, raises=AttributeError, reason="#14: extra instance state is discarded")
def test_pickle_preserves_extra_instance_state():
    predicate = Query({"x": 1})
    predicate.tag = "tag"
    restored = pickle.loads(pickle.dumps(predicate))
    assert restored.tag == "tag"
    assert restored.test({"x": 1}) is True
