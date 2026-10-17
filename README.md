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

Correctness tests do not run benchmarks. Run `uv run pytest benchmarks` explicitly
for CPU-only matching and construction benchmarks; see [the baseline](benchmarks/README.md).

Amp orbs use `.agents/setup` to install the locked Python dependencies and a
native MongoDB 7 server into the reusable project snapshot. `.agents/resume`
ensures the supervised MongoDB service is running after activation and wake;
it does not reinstall dependencies. MongoDB listens only on loopback, requires
no credentials, and stores disposable test data in `.amp/mongo/`.
Use `amp orb services ensure` to start or repair it manually and
`amp orb service logs mongo` to inspect its logs.

## Usage

Test if an input satisfies a query.

`Query(query)` deep-copies and validates the entire query and compiles its regex
patterns and field paths. Construct once and reuse `test` across documents.
Invalid or unsupported queries raise `InvalidQuery`, a `ValueError`
subclass, at construction—even inside `$not`, `$nor`, or an unused logical branch.
Mutating the original query afterward does not change the predicate.
There is no separate `validate()` method: replace `Query(q).validate()` with `Query(q)`.

For a valid query, `test(document)` returns `True` or `False` when evaluation
succeeds, and raises the original exception if evaluation fails. Documents must
be dicts; other inputs raise `TypeError`. Unsupported operators (for example
`$type`) and value/operator-form `$elemMatch` (`{"$elemMatch": {"$gt": 1}}`) are rejected.

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
  unsupported queries raise `InvalidQuery`, even in branches evaluation might skip.
- `test(document)` returns `True` or `False` for a valid query if evaluation succeeds.
- Operators stop once the result is decided: array matching stops at a match,
  `$or` stops at a true branch, and `$and` stops at a false branch. This also applies
  to implicit conjunctions, membership operands, and negation. There is **no
  promise to check every value**; an error in an unreached value does not surface.
- A reached evaluation error raises its **original exception**, without wrapping
  it or turning it into a non-match, including under `$not`, `$nor`, and `$or`.
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

## Regex subset and trust boundary

Regex matching uses Python's standard-library `re`, **not MongoDB's PCRE2 engine**.
Patterns must be strings or compiled string patterns. `$options` accepts `i`, `m`,
`s`, `x`, and `u` (`u` is accepted as a no-op, as MongoDB already uses UTF-8).
Do not combine options in a compiled pattern with nonempty `$options`.
Patterns compile when constructing `Query`, including implicit regexes, `$not`,
and regex entries in `$in`/`$nin`.

Matching uses `re.ASCII`: `\w`, `\d`, and word boundaries have ASCII semantics,
consistent with MongoDB 7 and 8 defaults. This also limits Python's whitespace
classes and case-insensitive matching; non-ASCII case folding can differ from
MongoDB. Inline Unicode modes and PCRE-only features are not portable.
Use Python named groups `(?P<name>...)`; PCRE spelling `(?<name>...)` is rejected,
not rewritten (a textual replacement could change escaped text or character classes).
Use syntax supported by your Python version; this is not full regex compatibility.
Malformed or unsupported patterns and flags raise `InvalidQuery`.
An actual NUL character in a pattern is rejected; escaped syntax such as
`r"a\0b"` remains valid and can match a NUL in a document string.

An implicit compiled regex or a regex in `$in` matches strings as a pattern.
It also compares regex-valued fields literally, retaining the original pattern
and flags separately from the ASCII string matcher.
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

Conditions on the same path can match different elements. `$all` requires each
operand to match independently, even across different subdocuments reached by a
path. It uses the same equality and regex rules as other matching; a single
requirement can also match a scalar (`{"x": {"$all": [1]}}` matches `{"x": 1}`).
Empty `$all` never matches. Use document-form `$elemMatch` when several conditions
must hold on the **same element**. `$size` tests the whole leaf array, without
adding the sizes of different candidates.

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
in order rather than using a hash set or sorted lookup.

```python
from datetime import date
from decimal import Decimal
from mgqpy import Query

predicate = Query({"x": {"$all": [{"day": "2024-08-01", "cost": ["3.14"]}]}})
assert predicate.test({"x": [{"day": date(2024, 8, 1), "cost": [Decimal("3.14")]}]})
```

## Known differences and limits

MongoDB does not perform these native/string conversions. `Decimal("0.1")`
equals `0.1` here; BSON Decimal128 `0.1` sorts below the binary float in MongoDB.
Python dates/datetimes retain their precision and Python comparison semantics:
there is no BSON millisecond truncation or automatic naive/aware datetime
alignment. Only an ISO string paired with an aware datetime inherits its zone.

This is not a BSON implementation: driver-specific types such as ObjectId,
Timestamp, MinKey/MaxKey, Decimal128 and Binary subtypes are not emulated.
Use ordinary Python values; tuples, custom classes and other non-BSON values
retain Python fallback behavior, not a MongoDB compatibility guarantee.
There is no collation support. The regex subset and its trust boundary are
described above. Numeric-path candidate order also differs from MongoDB, as
noted in the evaluation contract.
Trailing-empty path segments (such as `x.`) can differ from MongoDB 7/8.

`$mod` truncates numeric operands and document values toward zero and gives the
remainder the dividend's sign. Like MongoDB, it requires signed 64-bit-convertible
operands; booleans, non-finite values, and out-of-range document numbers do not match.
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
