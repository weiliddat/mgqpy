# Changelog

## 1.0.0

Changes from 0.9.0, implemented in [#12](https://github.com/weiliddat/mgqpy/pull/12),
[#13](https://github.com/weiliddat/mgqpy/pull/13),
[#16](https://github.com/weiliddat/mgqpy/pull/16),
[#18](https://github.com/weiliddat/mgqpy/pull/18) and
[#19](https://github.com/weiliddat/mgqpy/pull/19).
See the [migration notes](MIGRATING.md) before upgrading.

### Breaking changes

- Removed `validate()`. `Query(query)` now copies and validates the entire query,
  including unused branches, and raises `InvalidQuery` for invalid or unsupported queries.
- The public API is exactly `Query` and `InvalidQuery`, imported from `mgqpy`.
  Removed `mgqpy.utils.coerce`; native conversion is now part of matching,
  including within containers.
- `test(document)` raises reached evaluation errors unchanged, including under
  negation. Non-dict documents raise `TypeError`.
- Regex matching uses a Python `re` subset with `re.ASCII`, not PCRE2.
  Patterns must be trusted; validation does not bound matching time.

### Behaviour changes

- Matching short-circuits once the result is decided; skipped values are not checked.
- Field-expression operators run in fixed internal order, not dict insertion
  order. A range can precede an `$exists` guard and raise a reached error;
  use explicit `$and` clauses in the required order for guards.
- Booleans are distinct from numbers. Embedded-document equality includes key
  order. Containers use BSON ordering, and NaNs follow MongoDB equality/range rules.
- Array paths search immediate subdocuments without flattening nested arrays.
  Numeric segments try the index first, then literal numeric-field alternatives;
  `$exists` uses the same paths.
- Empty path components remain literal object keys. A final empty component at
  an array exhausts the path; after an array index it offers the selected array's
  immediate members and the array itself, without recursive flattening.
- Value-form `$elemMatch` is now supported: all child operators test the same raw
  element. Searching nested arrays requires explicit nested `$elemMatch`.
- `$all` uses shared equality and independent requirements over one lazy path walk;
  empty `$all` never matches.
- Date/datetime, Decimal and UUID conversions apply pairwise inside containers
  too. A naive ISO string inherits its paired datetime's timezone.

### Fixes

- Corrected `$mod` truncation and signed remainders, canonical ASCII array indices,
  `$size` bounds, literal regex equality, NUL-pattern rejection and Python 3.10 regex support.
- Literal documents with later `$` keys validate correctly. Nested query errors
  report their location.
- `Decimal("sNaN")` document values no longer raise in `$mod` (they do not match),
  and `$exists` accepts signaling NaN as a truthy numeric operand.

### Performance

- Construction prepares paths, predicates, regexes and numeric operands for reuse.
  It costs more than 0.9.0's unchecked reference assignment: compile once, test many.
- Selected singleton `$all` queries compile directly to their child predicate;
  exact number/string requirements retain chunked membership.

Matching-time ratios, **1.0 / 0.9.0** (lower is faster), across CPython 3.10–3.13.
Scans use 100 members unless noted.

| Matching | Ratio |
| --- | ---: |
| Flat equality | 0.31–0.35× |
| Mixed numeric range, last hit | 0.10–0.13× |
| `$in`, last of 1,000 | 0.20–0.27× |
| Numeric `$all`, late hit | 0.87–1.04× |
| Ordered-document equality, late hit/miss | 1.40–1.54× |
| Numeric-index miss | 7.24–9.43× |
| Singleton `$all` over documents, late hit/miss | 12.17–19.14× |
| Singleton `$all` over arrays, late hit/miss | 9.30–16.27× |

Construction is the up-front cost; reuse `Query` objects. Reuse does not remove
the slower per-match costs above. These are shared-orb observations, not
performance guarantees. Full measurements and method: [benchmarks](benchmarks/README.md).

### Known differences

- Python regex, native conversions, datetime precision/awareness and Python-only
  types do not fully match MongoDB. `$type` remains unsupported.
  Cross-version query pickles are not supported.
  See [README limits](README.md#known-differences-and-limits) and
  [#14](https://github.com/weiliddat/mgqpy/issues/14) for open questions;
  these are not promises of future parity.
