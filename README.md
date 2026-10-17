# mgqpy

[![codecov](https://codecov.io/gh/weiliddat/mgqpy/graph/badge.svg?token=CuQS0w5IkL)](https://codecov.io/gh/weiliddat/mgqpy)
![PyPI - Version](https://img.shields.io/pypi/v/mgqpy)

[MongoDB query](https://www.mongodb.com/docs/manual/reference/operator/query/) as a predicate function

This aims to be consistent with how MongoDB's matches documents. This includes traversal across nested dicts and lists, None and field-presence/absence handling.

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
patterns. Invalid or unsupported queries raise `InvalidQuery`, a `ValueError`
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
    print(error)  # $in operator value must be a list
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
- Regex patterns must come from **trusted sources**; see the trust boundary below.

Ordinary scalar type mismatches (such as a string against a numeric range operand)
remain non-matches. Container comparisons and Python-native values can still
fail. These examples reproduce exceptions callers can encounter; they are not
an exhaustive list:

```python
from mgqpy import Query

# TypeError: deferred container comparison tries to compare "z" > 1.
Query({"x": {"$gt": {"a": 1}}}).test({"x": {"a": "z"}})

# TypeError: the top-level document must be a dict.
Query({}).test([])
```

```python
import sys
from mgqpy import Query

# RecursionError: matching recurses through a document deeper than Python's limit.
value = 0
for _ in range(sys.getrecursionlimit()):
    value = [value]
Query({"x": 1}).test({"x": value})
```

```python
from decimal import Decimal
from mgqpy import Query

# decimal.InvalidOperation: ordering Decimal NaN, with the default decimal traps.
Query({"x": {"$gt": 0}}).test({"x": Decimal("NaN")})
```

Short-circuiting can avoid a failing comparison, but does not validate a document:

```python
from mgqpy import Query

query = Query({"$or": [{"ok": True}, {"x": {"$gt": {"a": 1}}}]})
assert query.test({"ok": True, "x": {"a": "z"}}) is True
query.test({"ok": False, "x": {"a": "z"}})  # TypeError: comparison is reached.
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

## Compatibility limits in this v1 base

Array indices must be canonical ASCII numbers (`0`, `1`, `2`, …). `00`, `²`, and
other noncanonical segments remain ordinary field names, not array indices.
`$mod` truncates numeric operands and document values toward zero and gives the
remainder the dividend's sign. Like MongoDB, it requires signed 64-bit-convertible
operands; booleans, non-finite values, and out-of-range document numbers do not match.
`$size` requires a finite integral number in `0..2147483647` (including `2.0`).

Traversal and value comparison otherwise retain the 0.9.0 behaviour. Known
differences remain for nested/mixed arrays, BSON container ordering, bool/number
equality, embedded-document key order, NaN equality, `$all`, and the scope of
date/Decimal/UUID conversions. These are not MongoDB-conformance guarantees.
In particular, valid container range queries can raise `TypeError` instead of
following MongoDB's BSON ordering; see the evaluation-error examples above.

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
