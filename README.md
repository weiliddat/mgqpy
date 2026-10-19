# mgqpy

[![codecov](https://codecov.io/gh/weiliddat/mgqpy/graph/badge.svg?token=CuQS0w5IkL)](https://codecov.io/gh/weiliddat/mgqpy)
![PyPI - Version](https://img.shields.io/pypi/v/mgqpy)

[MongoDB query](https://www.mongodb.com/docs/manual/reference/operator/query/) as a predicate function

Match Python dicts and lists with MongoDB-style queries. Python 3.10+, no runtime
dependencies. The supported operators are checked against real MongoDB 7 and 8;
Python-native conversions and other known differences are documented below.

## Installation

```sh
pip install mgqpy
```

Upgrading from 0.9.0? Read the [migration notes](MIGRATING.md) and
[1.0.0 changelog](CHANGELOG.md#100).

## Usage

Compile once, test many: `Query(query)` deep-copies and validates the query and
compiles its regex patterns and field paths. Reuse `Query` objects: construction
is the up-front cost, not part of each match. Mutating the original query
afterward does not change the predicate.
Invalid queries raise `InvalidQuery` at construction. `test(document)` returns
a bool on success and raises reached evaluation errors, rather than treating
them as non-matches. See the [evaluation contract](#evaluation-contract).

The public API is exactly `Query` and `InvalidQuery`, imported from `mgqpy`.
The former `mgqpy.utils.coerce` helper is removed; native conversion is part of
matching, including within containers.

```python
from mgqpy import Query

predicate = Query({"foo.bar": {"$gt": 1}})

inputs = [
    {"foo": [{"bar": [1, 2]}]},
    {"foo": {"bar": 1}},
    {"foo": {"bar": 2}},
    {"foo": None},
]

filtered = filter(predicate.test, inputs)

assert list(filtered) == [
    {"foo": [{"bar": [1, 2]}]},
    {"foo": {"bar": 2}},
]
```

Handle invalid queries at construction:

```python
from mgqpy import InvalidQuery, Query

try:
    predicate = Query({"foo": {"$in": 1}})
except InvalidQuery as error:
    print(error)  # query.foo: $in operator value must be a list
```

## Evaluation contract

- `Query(query)` copies and validates the entire query up front. Invalid or
  unsupported queries raise `InvalidQuery` (a `ValueError` subclass), even in
  branches evaluation might skip. There is no separate `validate()` method.
  Unsupported operators include `$type`. Both document-form and value-form
  `$elemMatch` are supported.
- `test(document)` returns `True` or `False` for a valid query if evaluation succeeds.
  Documents must be dicts; other inputs raise `TypeError`.
- Operators stop once the result is decided: array matching stops at a match,
  `$or` stops at a true branch, and `$and` stops at a false branch. This also applies
  to implicit conjunctions, membership operands, and negation. There is **no
  promise to check every value**; an error in an unreached value does not surface.
- A reached evaluation error raises its **original exception**, without wrapping
  it or turning it into a non-match, including under `$not`, `$nor`, and `$or`.
- Operators within one field expression run in a fixed internal order, not dict
  insertion order. A range can run before an `$exists` guard even if the guard
  appears first. Use explicit `$and` clauses for ordered guards.
- Numeric array paths try the index before numeric-field alternatives; candidate order is not MongoDB's and skipped candidates are not checked.
- Comparison-method call order on non-BSON custom types is not guaranteed; reached exceptions still propagate.
- Regex patterns must come from **trusted sources**; see the trust boundary below.

Ordinary scalar type mismatches (such as a string against a numeric range operand)
remain non-matches. Python-native values and custom classes can still fail.
For example, Python cannot order an aware datetime against a naive datetime:

```python
from datetime import datetime, timezone
from mgqpy import Query

predicate = Query({"x": {"$gt": datetime(2024, 8, 1)}})
predicate.test({"x": datetime(2024, 8, 2, tzinfo=timezone.utc)})  # TypeError

# TypeError: the top-level document must be a dict.
Query({}).test([])
```

Short-circuiting can avoid a failing comparison, but does not validate a document:

```python
from datetime import datetime, timezone
from mgqpy import Query

query = Query({"$or": [{"ok": True}, {"x": {"$gt": datetime(2024, 8, 1)}}]})
value = datetime(2024, 8, 2, tzinfo=timezone.utc)
assert query.test({"ok": True, "x": value}) is True
query.test({"ok": False, "x": value})  # TypeError: comparison is reached.
```

For example, `{"x": {"$exists": False, "$gt": datetime(2024, 8, 1)}}` still
raises on that aware datetime. To run the guard first:

```python
guarded = Query({"$and": [
    {"x": {"$exists": False}},
    {"x": {"$gt": datetime(2024, 8, 1)}},
]})
assert guarded.test({"x": value}) is False
```

## Regex subset and trust boundary

Regex matching uses Python's standard-library `re`, **not MongoDB's PCRE2 engine**.
Patterns must be strings or compiled string patterns. `$options` accepts `i`, `m`,
`s`, `x`, and `u` (`u` is accepted as a no-op, as MongoDB already uses UTF-8).
Do not combine options in a compiled pattern with nonempty `$options`.
Patterns compile when constructing `Query`, including implicit regexes, `$not`,
and regex entries in `$in`/`$nin`.

Matching uses Python's default Unicode semantics. Case-insensitive patterns match
non-ASCII text: `"^über$"` with `$options: "i"` matches `"Über"`. Like MongoDB,
this does not expand `ß` to `SS`.
Unlike MongoDB 7 and 8 defaults, `\w`, `\d`, `\s`, and `\b` use Unicode word,
digit, whitespace, and word-boundary rules. Python's global regex flags cannot
combine Unicode case folding with ASCII-only classes; mgqpy keeps Unicode matching.
Explicit ASCII modes in supplied patterns still follow Python `re`.
Use Python named groups `(?P<name>...)`; PCRE spelling `(?<name>...)` is rejected,
not rewritten (a textual replacement could change escaped text or character classes).
Use syntax supported by your Python version; this is not full regex compatibility.
Malformed or unsupported patterns and flags raise `InvalidQuery`.
An actual NUL character in a pattern is rejected; escaped syntax such as
`r"a\0b"` remains valid and can match a NUL in a document string.

An implicit compiled regex or a regex in `$in` matches strings as a pattern.
It also compares regex-valued fields literally, retaining the original pattern
and flags separately from the string matcher.
Explicit `$eq` with a compiled regex compares the regex as a literal value.

**Patterns must come from trusted sources.** Validation checks syntax, not runtime
cost. Python `re` has no matching timeout; catastrophic backtracking can block the
calling thread, especially with long or adversarial document strings. Do not pass
untrusted patterns directly to mgqpy; input limits alone do not guarantee safety.

## Paths and array matching

Paths are compiled once. Dict fields are followed directly; intermediate arrays
search immediate subdocuments, not nested arrays or scalar elements. A missing
field can match null, but a skipped scalar array element is not a missing field:
`{"x.y": None}` matches `{"x": 1}`, not `{"x": [1]}`. Leaf arrays offer their
immediate elements and the whole array; an explicit terminal index offers only
the selected value. Numeric segments also search literal fields in immediate
subdocuments, so `{"x.0": 1}` matches `{"x": [{"0": 1}]}`.

Array indices must be canonical ASCII numbers (`0`, `1`, `2`, …). `00`, `²`, and
other noncanonical segments remain ordinary field names, not array indices.
`$exists` uses the same path rules and tests presence, including null and empty
arrays. Negation means no candidate matches, not that some candidate fails.

Empty path components are literal empty field names on objects. At an array,
a single remaining empty component exhausts the path: `{"x.": 5}` matches
`{"x": [5]}` and `{"x": {"": 5}}`, not `{"x": [{"": 5}]}`. Operators keep their
usual leaf rules there, so `{"x.": {"$exists": True}}` matches `{"x": []}`.
Repeated dots are preserved; `x..y` still looks up the empty key between `x` and `y`.

After an array index, a final empty component offers the selected array's
immediate members and the array itself to every operator. Thus
`{"x.0.": {"$size": 0}}` matches `{"x": [[[]]]}`, unlike `x.` or terminal `x.0`.
This does not flatten recursively: `{"x.0.": 1}` still does not match
`{"x": [[[1]]]}`.

Conditions on the same path can match different elements. `$all` requires each
operand to match independently, even across different subdocuments reached by a
path. With multiple requirements it walks the path once and reuses reached leaf values,
stopping once every requirement has matched. It uses the same equality and regex rules
as other matching; a single requirement can also match a scalar
(`{"x": {"$all": [1]}}` matches `{"x": 1}`).
Empty `$all` never matches. `$size` tests the whole leaf array, without adding the
sizes of different candidates.

`$elemMatch` binds conditions to the **same immediate element** in two forms:

- Document form treats each object or array element as a document (arrays expose
  numeric fields): `{"x": {"$elemMatch": {"a": 1, "b": 2}}}` requires both fields on
  one element. Logical `$and`/`$or`/`$nor` children also use document form.
- Value form applies each operator to the raw element, without another array
  expansion: `{"x": {"$elemMatch": {"$gt": 1, "$lt": 3}}}` matches `[0, 2, 4]`,
  not `[[2]]`. Use an explicit nested `$elemMatch` to search a nested array;
  `$size` can test that raw array directly.

An inner `$not` means some element fails its predicate; an outer `$not` means no
element satisfies `$elemMatch`. Empty arrays fail the inner form and satisfy the
outer form. Inside value form, `$all: [1, 2]` means direct equality to both `1` and
`2`, so `[[1, 2]]` does not match; `$all: [[1, 2]]` does. An outer `$all` of
`$elemMatch` requirements can use separate elements for each requirement.

## Value comparison

- Booleans are separate from numbers: `True` does not equal `1`. Integers and
  floats compare numerically without casting large integers to float.
- Embedded dict equality includes **key order**, recursively. The first key
  classifies an expression: `{"a": 1, "$eq": 2}` is a literal document, including
  inside `$all`; an expression starts with a `$` key.
- Ranges compare scalar values in the same BSON type bracket. Arrays compare
  lexicographically. Embedded documents compare each entry's **value type, then
  key, then value**, in insertion order; an equal prefix sorts before its extension.
  Inside these containers, unlike scalar query ranges, different value types
  follow BSON order: null, number, string, document, array, binary, bool, date,
  regex (for the types represented here).
- NaN equals NaN, including inside arrays and documents. Direct `$gt`/`$lt` with
  NaN never match; `$gte`/`$lte` match only when both values are NaN. **Inside
  containers**, NaN sorts below all other numbers, including negative infinity.

These rules are shared by equality, membership, ranges, `$all`, and their
negations. They replace 0.9.0's Python bool/number equality, order-insensitive
dict equality, and container range errors.

## Python-native conversions

Conversions happen at each **scalar pair**, in either direction, including
inside dicts and lists and in every operator that uses value equality or ranges:

| Paired values | Rule |
| --- | --- |
| `date` or `datetime` and a string | Parse using the paired type's `fromisoformat` (formats depend on Python version). A date-only string becomes midnight when paired with a datetime. |
| Aware `datetime` and a naive ISO string | The string inherits **that datetime's timezone**, never the host timezone. An explicit offset is preserved. |
| `Decimal` and int, float or string | Convert the other value with `Decimal(str(value))`. Bool is excluded. Decimal NaNs follow the NaN rules above, including signaling NaNs. |
| `UUID` and a string | Parse the string as a UUID; compact and hyphenated spellings work. |

Invalid conversion leaves the original types, so a scalar type mismatch does
not match. Strings paired with strings stay strings. This is pairwise conversion,
not global normalization: two differently formatted strings may each equal a
native value without equaling each other. Membership therefore checks operands
in order rather than normalizing them into a hash set. Only a list made entirely of
exact `None`, `int`, `float` and `str` operands is looked up by hash, with the same result.

```python
from datetime import date
from decimal import Decimal
from mgqpy import Query

predicate = Query({"x": {"$all": [{"day": "2024-08-01", "cost": ["3.14"]}]}})
assert predicate.test({"x": [{"day": date(2024, 8, 1), "cost": [Decimal("3.14")]}]})
```

## Known differences and limits

See [#14](https://github.com/weiliddat/mgqpy/issues/14) for the remaining
differences and open questions. These are not promises of future MongoDB parity.

MongoDB does not perform these native/string conversions. `Decimal("0.1")`
equals `0.1` here; BSON Decimal128 `0.1` sorts below the binary float in MongoDB.
Python dates/datetimes retain their precision and Python comparison semantics:
there is no BSON millisecond truncation or automatic naive/aware datetime
alignment. Only an ISO string paired with an aware datetime inherits its zone.

This is not a BSON implementation: driver-specific types such as ObjectId,
Timestamp, MinKey/MaxKey, Decimal128 and Binary subtypes are not emulated.
Use ordinary Python values; tuples, custom classes and other non-BSON values
retain Python fallback behavior, not a MongoDB compatibility guarantee.
When either scalar has no supported BSON type, equality and ranges use Python
comparisons, including comparisons between custom base and subclass instances.
Non-BSON partial orders (such as disjoint sets) can compare as ties inside containers.
There is no collation support. The regex subset and its trust boundary are
described above. Numeric-path candidate order also differs from MongoDB, as
noted in the evaluation contract.
NUL characters in field keys are accepted here but cannot be encoded as BSON keys.

Ordinary `Query` instances support pickling and process-pool use within the same
version. Rebuild queries from their source after upgrading; cross-version pickles
are not supported. Extra instance attributes are not preserved, and subclasses
with extra constructor arguments need their own pickle protocol.

`$mod` truncates numeric operands and document values toward zero and gives the
remainder the dividend's sign. Like MongoDB, it requires signed 64-bit-convertible
operands; invalid query operands raise `InvalidQuery`. Booleans, non-finite values,
and out-of-range document numbers do not match.
`$size` requires a finite integral number in `0..2147483647` (including `2.0`).

## Supported operators

Comparison query operators

- [x] \$eq
- [x] \$eq (implicit), e.g. `{"foo": None}`
- [x] \$ne
- [x] \$gt
- [x] \$gte
- [x] \$lt
- [x] \$lte
- [x] \$in
- [x] \$nin

Logical query operators

- [x] \$and
- [x] \$and (implicit), e.g. `{"foo": 1, "bar": "baz"}`
- [x] \$or
- [x] \$not
- [x] \$nor

Element query operators

- [x] \$exists

Evaluation query operators

- [x] \$regex
- [x] \$regex (implicit), e.g. `{"foo": re.compile('^bar')}`
- [x] \$mod

Array query operators

- [x] \$all
- [x] \$elemMatch
- [x] \$size

## Development

Install development dependencies with `uv sync --locked --dev`. Tests compare
results against a disposable MongoDB on loopback port 27017. Outside an Amp orb,
start MongoDB 7 with `docker compose up --detach --wait`, then run `uv run pytest`.
To use MongoDB 8, stop Compose first and run
`MONGODB_VERSION=8 docker compose up --detach --wait`.
Set `MONGODB_URI` to test another disposable local server. Tests create a unique
database per run/worker and collection per case, clean up only their namespaces,
and close the client. CI tests Python 3.10–3.13 against MongoDB 7 and 8, including
an isolated installed-wheel smoke test.

Correctness tests do not run performance benchmarks. Use `python benchmarks/run.py`
to compare git refs; see [the baseline](benchmarks/README.md) for commands, cases,
construction/matching/single-use results and historical measurements.

Amp orbs use `.agents/setup` to install the locked Python dependencies and a
native MongoDB 7 server into the reusable project snapshot. `.agents/resume`
ensures the supervised MongoDB service is running after activation and wake;
it does not reinstall dependencies. MongoDB listens only on loopback, requires
no credentials, and stores disposable test data in `.amp/mongo/`.
Use `amp orb services ensure` to start or repair it manually and
`amp orb service logs mongo` to inspect its logs.
