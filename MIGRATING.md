# Migrating from 0.9.0 to 1.0.0

The public API is exactly `Query` and `InvalidQuery`, imported from `mgqpy`.
The previously exported `mgqpy.utils.coerce` helper has been removed. Native
conversion is now part of matching, including within containers; do not import
internal conversion helpers as a replacement.

## Compile once, test many

Remove calls to `validate()`. Construction now deep-copies and validates the
whole query, including branches that will not be evaluated, and prepares it for
repeated matching. Catch `InvalidQuery` at construction, not around `validate()`.
Changing the original query no longer changes an existing predicate; construct a
new `Query` when the filter changes.

Before (0.9.0):

```python
from mgqpy import Query

predicate = Query({"score": {"$gte": 10}}).validate()
matches = [doc for doc in documents if predicate.test(doc)]
```

After (1.0.0):

```python
from mgqpy import InvalidQuery, Query

try:
    predicate = Query({"score": {"$gte": 10}})
except InvalidQuery as error:
    raise ValueError(f"Invalid filter: {error}") from error

matches = [doc for doc in documents if predicate.test(doc)]
```

`InvalidQuery` is a `ValueError` subclass. Invalid or unsupported queries no
longer silently return `False`, even in unused logical branches. `$type` remains
unsupported. Both document-form and value-form `$elemMatch` now work.

## Evaluation errors are not non-matches

`test(document)` requires a dict and returns a bool when evaluation succeeds.
A reached error now raises its original exception, including under negation.
For example, ordering an aware datetime against a naive datetime raises
`TypeError`. If your application wants to skip such documents, handle the
specific errors it expects around `test()`; do not confuse them with invalid queries.

Matching stops when the result is decided. An error in a skipped branch or
array element will not surface. `test()` is not document validation; see the
[evaluation contract and examples](README.md#evaluation-contract).

Operators in one field expression run in a fixed internal order, not dict
insertion order. A range operator can run before an `$exists` guard even when
the guard is written first; a reached error still propagates. Use explicit
`$and` clauses in the required order for guards. For example:

```python
from datetime import datetime, timezone
from mgqpy import Query

value = datetime(2024, 8, 2, tzinfo=timezone.utc)
# This raises TypeError: the range runs before $exists.
Query({"x": {"$exists": False, "$gt": datetime(2024, 8, 1)}}).test({"x": value})

# The first clause now decides the result before the range is reached.
guarded = Query({"$and": [
    {"x": {"$exists": False}},
    {"x": {"$gt": datetime(2024, 8, 1)}},
]})
assert guarded.test({"x": value}) is False
```

## Recheck filters that depend on these semantics

- **Regex:** matching uses Python `re`, not MongoDB's PCRE2. In 1.0.1, the default
  Unicode semantics restore 0.9.0's non-ASCII case-insensitive matching; 1.0.0
  forced `re.ASCII`. Character classes `\w`, `\d`, `\s`, and word boundaries
  `\b` now use Unicode rules, unlike MongoDB 7 and 8 defaults.
  PCRE-only syntax is not translated; rejected patterns raise `InvalidQuery`.
  Explicit `$eq` compares compiled regexes literally; implicit regexes and regex
  entries in `$in` also match strings. Use only trusted patterns: syntax validation
  does not prevent catastrophic backtracking or impose a timeout.
- **Booleans and numbers:** `{"x": 1}` no longer matches `{"x": True}`.
  Integers and floats still compare numerically without losing large-integer precision.
- **Key order and ranges:** embedded dict equality is order-sensitive, recursively.
  `{"x": {"a": 1, "b": 2}}` does not match `{"x": {"b": 2, "a": 1}}`.
  Arrays and documents now support BSON range ordering. NaN equals NaN;
  direct strict ranges with NaN never match, while NaN sorts below other numbers
  inside containers. See [value comparison](README.md#value-comparison).
- **Array traversal:** intermediate arrays search immediate subdocuments, not
  nested arrays or scalar elements. `{"x.y": None}` matches `{"x": 1}` but not
  `{"x": [1]}`. Numeric segments also search literal numeric fields:
  `{"x.0": 1}` matches `{"x": [{"0": 1}]}`. Only canonical ASCII numbers are
  indices; `$exists` follows the same rules. See [paths](README.md#paths-and-array-matching).
- **Empty path components:** these are literal empty keys on objects. At an array,
  a final empty component exhausts the path: `{"x.": 5}` matches `{"x": [5]}`
  and `{"x": {"": 5}}`, not `{"x": [{"": 5}]}`. After an array index, a final
  empty component offers immediate members and the selected array to every
  operator: `{"x.0.": {"$size": 0}}` matches `{"x": [[[]]]}`. It does not
  recursively flatten arrays. Repeated dots still address literal empty keys.
- **`$elemMatch`:** value form is now supported. For example,
  `{"x": {"$elemMatch": {"$gt": 1, "$lt": 3}}}` matches `{"x": [0, 2, 4]}`,
  not `{"x": [0, 4]}` or `{"x": [[2]]}`. Every operator tests the same raw
  element; use explicit nested `$elemMatch` to search nested arrays. An inner
  `$not` asks for an element that fails its predicate; an outer `$not` asks that
  no element satisfy `$elemMatch`.
- **`$all`:** requirements match independently using shared equality, even across
  subdocuments reached by a path. A single requirement can match a scalar;
  empty `$all` never matches. Use `$elemMatch` for conditions that must hold on one
  element. Inside value-form `$elemMatch`, `$all: [1, 2]` tests direct equality to
  both values, not membership in a nested array; `$all: [[1, 2]]` can match the
  raw array `[1, 2]`.
- **`$mod`:** operands and document values truncate toward zero; the remainder
  has the dividend's sign. `{"x": {"$mod": [3, -1]}}` matches `{"x": -4}`.
  Invalid query operands raise `InvalidQuery`; booleans, non-finite values and
  out-of-int64 document numbers do not match.
- **Native conversions:** date/datetime, Decimal and UUID conversions now apply
  pairwise inside dicts and lists too. A naive ISO string paired with an aware
  datetime inherits that datetime's timezone, not the host timezone. Failed
  conversions leave the original types. These are Python conveniences, not
  MongoDB coercion; see [conversion rules](README.md#python-native-conversions).

Rebuild persisted queries from their source after upgrading; 0.9.0 query pickles
are not compatible. Ordinary same-version `Query` pickling/process-pool use works,
but extra instance state is not preserved and subclasses may need their own protocol.

The [changelog](CHANGELOG.md#performance) records performance tradeoffs.
Construction is up-front work, so reuse `Query` objects; reuse does not remove
the slower per-match costs listed there. Remaining
differences and open questions are in [#14](https://github.com/weiliddat/mgqpy/issues/14);
they are not promises of future MongoDB parity.
