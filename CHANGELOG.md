# Changelog

## 1.0.0

Changes from 0.9.0, implemented in [#12](https://github.com/weiliddat/mgqpy/pull/12),
[#13](https://github.com/weiliddat/mgqpy/pull/13) and
[#16](https://github.com/weiliddat/mgqpy/pull/16).
See the [migration notes](MIGRATING.md) before upgrading.

### Breaking changes

- Removed `validate()`. `Query(query)` now copies and validates the entire query,
  including unused branches, and raises `InvalidQuery` for invalid or unsupported queries.
- `test(document)` raises reached evaluation errors unchanged, including under
  negation. Non-dict documents raise `TypeError`.
- Regex matching uses a Python `re` subset with `re.ASCII`, not PCRE2.
  Patterns must be trusted; validation does not bound matching time.

### Behaviour changes

- Matching short-circuits once the result is decided; skipped values are not checked.
- Booleans are distinct from numbers. Embedded-document equality includes key
  order. Containers use BSON ordering, and NaNs follow MongoDB equality/range rules.
- Array paths search immediate subdocuments without flattening nested arrays.
  Numeric segments try the index first, then literal numeric-field alternatives;
  `$exists` uses the same paths.
- `$all` uses shared equality and independent requirements over one lazy path walk;
  empty `$all` never matches.
- Date/datetime, Decimal and UUID conversions apply pairwise inside containers
  too. A naive ISO string inherits its paired datetime's timezone.

### Fixes

- Corrected `$mod` truncation and signed remainders, canonical ASCII array indices,
  `$size` bounds, literal regex equality, NUL-pattern rejection and Python 3.10 regex support.
- Literal documents with later `$` keys validate correctly. Nested query errors
  report their location.

### Performance

- Construction prepares paths, predicates, regexes and numeric operands for reuse.
  It costs more than 0.9.0's unchecked reference assignment: compile once, test many.
- Recorded benchmarks show faster matching in the original workloads, with costs
  for ordered-document equality, some `$all` cases, late/missing `$size` and
  `$exists`, and indexed misses. See [measurements and limits](benchmarks/README.md);
  these are not performance guarantees.

### Known differences

- Python regex, native conversions, datetime precision/awareness, trailing-empty
  paths and Python-only types do not fully match MongoDB. `$type` and value-form
  `$elemMatch` remain unsupported. Cross-version query pickles are not supported.
  See [README limits](README.md#known-differences-and-limits) and
  [#14](https://github.com/weiliddat/mgqpy/issues/14) for open questions;
  these are not promises of future parity.
