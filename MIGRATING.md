# Migrating from 0.9.0 to 1.0.0

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
longer silently return `False`, even in unused logical branches. `$type` and
value-form `$elemMatch` remain unsupported; document-form `$elemMatch` works.

## Evaluation errors are not non-matches

`test(document)` requires a dict and returns a bool when evaluation succeeds.
A reached error now raises its original exception, including under negation.
For example, ordering an aware datetime against a naive datetime raises
`TypeError`. If your application wants to skip such documents, handle the
specific errors it expects around `test()`; do not confuse them with invalid queries.

Matching stops when the result is decided. An error in a skipped branch or
array element will not surface. `test()` is not document validation; see the
[evaluation contract and examples](README.md#evaluation-contract).

## Recheck filters that depend on these semantics

- **Regex:** matching uses Python `re` with `re.ASCII`, not MongoDB's PCRE2.
  Character classes and case folding can change, especially for non-ASCII text.
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
- **`$all`:** requirements match independently using shared equality, even across
  subdocuments reached by a path. A single requirement can match a scalar;
  empty `$all` never matches. Use document-form `$elemMatch` for conditions that
  must hold on one element.
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

The [changelog](CHANGELOG.md#100) records performance tradeoffs. Remaining
differences and open questions are in [#14](https://github.com/weiliddat/mgqpy/issues/14);
they are not promises of future MongoDB parity.
