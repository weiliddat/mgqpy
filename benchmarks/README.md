# Matching and construction baseline

These CPU-only benchmarks are opt-in, independent of MongoDB and the correctness
suite. `uv run pytest` collects only `tests/`; run these explicitly:

```sh
uv run pytest benchmarks --benchmark-min-rounds=30 --benchmark-max-time=0.5 \
  --benchmark-warmup=on --benchmark-disable-gc --benchmark-json=/tmp/mgqpy-bench.json
```

`test_match` constructs the predicate outside the timed region and evaluates one
document per invocation, checking both matches and non-matches. `test_construct`
times only `Query(query)`; its assertion evaluates the result outside the timed
region. Regex construction uses Python's warm regex cache. Flat equality, a
five-segment dict path, 100 subdocuments, a 1,000-member `$in`, explicit regex,
and combined `$and`/`$or` each have both measurements. Additional cases cover single-/two-digit indexed paths,
scalar/deep `$size`, and scalar/deep/100-value-array `$mod`, also with construction
timings. Array `$mod` has both an early match and a last-element match to measure
short-circuiting separately from full-scan cost. Dataset definitions live in
`test_benchmarks.py`.

Mixed-numeric range matching adds 32 matching-only cases: `$gt`, `$gte`, `$lt`,
and `$lte`, each with an integer query operand/float document values and the
reverse. Each has a scalar match, scalar miss, 100-value array with only its last
element matching, and 100-value all-miss array. All use threshold 72; the array
prefix is 0 for greater-than queries and 99 for less-than queries. These cases
do not add redundant construction timings.

## 0.9.0 versus the initial v1 base

Measured on 2026-10-17 in the same Linux x86-64 Amp orb, CPython 3.11.6,
pytest-benchmark 5.2.3, Intel Xeon @ 2.60 GHz. Values are medians in microseconds
per invocation; lower is faster. Baseline source is
[0.9.0 on main](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d).
Both versions ran the same cases, interpreter, and options above, sequentially.
These are shared-VM observations, not performance guarantees or CI thresholds.

| Matching | 0.9.0 (µs) | v1 base (µs) |
| --- | ---: | ---: |
| Flat equality | 1.334 | 1.442 |
| Deep dict path | 2.177 | 2.402 |
| Arrays of subdocuments | 88.183 | 98.551 |
| Large `$in` | 648.033 | 710.833 |
| Regex | 2.137 | 1.297 |
| `$and`/`$or` | 6.390 | 6.408 |

| Construction | 0.9.0 (µs) | v1 base (µs) |
| --- | ---: | ---: |
| Flat equality | 0.116 | 2.148 |
| Deep dict path | 0.209 | 2.171 |
| Arrays of subdocuments | 0.119 | 2.177 |
| Large `$in` | 0.126 | 425.998 |
| Regex | 0.115 | 4.970 |
| `$and`/`$or` | 0.115 | 11.719 |

Construction deliberately costs more: 0.9.0 stored a reference without checking
it; the v1 base deep-copies and validates the whole query. Reuse predicates when
filtering many documents. The initial base took about 0.43 ms to copy/validate
1,000 `$in` operands. Regex matching avoids repeated flag parsing/compilation.
In this initial run, non-regex matching was about 8–12% slower, combined logical
matching was essentially unchanged, and regex matching was about 39% faster.
The interleaved recheck below confirms the regression and measures its fix.

To repeat the old-source comparison without changing the checkout, extract the
linked baseline commit's `src/` with `git archive` into a temporary directory.
Run the current benchmark file using the same interpreter with
`PYTHONPATH=/path/to/baseline/src .venv/bin/python -m pytest benchmarks ...`, then
run again without that `PYTHONPATH`. Check `mgqpy.__file__` before measuring so
the baseline run cannot accidentally import the editable installation.

## Interleaved recheck and small overhead fixes

Remeasured on 2026-10-17 with the same interpreter and orb. Six alternating
process pairs first confirmed a real matching slowdown: 0.9.0 versus the
initial base measured 1.398/1.488 µs (flat), 2.286/2.543 µs (deep),
90.139/98.867 µs (subdocuments), and 651.502/707.067 µs (large `$in`).

The final comparison below interleaved **0.9.0, the initial base, and the revised
base** at each workload/operation, rather than running whole suites sequentially.
Each source tree was imported independently, with its own module globals and
recursive matchers; source paths and function identities were checked. Timings
used `timeit`, disabled GC, 100 warmup calls, and 20 blocks with variant order
shuffled by `random.Random(4361)`. Matching iterations per block were
30,000/18,000/500/70/30,000/8,000 in the table's order. Construction used 15,000
iterations per block, except 200 for large `$in`. Values are medians of the
20 per-call block timings, including an identical lambda-call overhead for all
variants. The initial base is
[`1a49a5e`](https://github.com/weiliddat/mgqpy/commit/1a49a5e85c1fdd459297706fe9693487f181114c).

| Matching | 0.9.0 (µs) | Initial base (µs) | Revised base (µs) |
| --- | ---: | ---: | ---: |
| Flat equality | 1.396 | 1.521 | 1.365 |
| Deep dict path | 2.274 | 2.548 | 2.098 |
| Arrays of subdocuments | 91.607 | 101.004 | 85.465 |
| Large `$in` | 665.523 | 729.199 | 646.418 |
| Regex | 2.176 | 1.309 | 1.308 |
| `$and`/`$or` | 6.653 | 6.807 | 6.315 |

| Construction | 0.9.0 (µs) | Initial base (µs) | Revised base (µs) |
| --- | ---: | ---: | ---: |
| Flat equality | 0.157 | 2.364 | 1.051 |
| Deep dict path | 0.155 | 2.366 | 1.051 |
| Arrays of subdocuments | 0.158 | 2.373 | 1.068 |
| Large `$in` | 0.165 | 428.979 | 206.514 |
| Regex | 0.155 | 5.440 | 3.291 |
| `$and`/`$or` | 0.158 | 12.779 | 7.102 |

The equality matcher's regex-mode flag added recursive keyword calls and a
third comprehension closure cell on Python 3.10/3.11. Those cells were allocated
even on scalar calls. Positional recursion and explicit eager array loops remove
that cost; `test()` also no longer wraps the matcher's boolean result in `bool()`.
The revised four matching workloads are 2–8% faster than 0.9.0 in this run.
At this stage arrays still evaluated every element before `any()`, preserving
the then-current whole-document non-match policy on evaluation errors. The final
short-circuit evaluation contract below supersedes that policy.

Construction now copies built-in query containers while checking their keys in
the same walk, sharing only immutable scalars. Other native values and container
subclasses retain `deepcopy` behavior. Operator validation/regex preparation
remains a separate pass so aliased literal operands cannot be changed by regex
normalization. This halves large-`$in` construction cost (429 → 207 µs), without
changing validation or snapshot isolation. It still scales with operand count;
0.9.0's unchecked reference assignment is not a comparable construction contract.
These remain shared-VM measurements, not performance guarantees or thresholds.

## Numeric and indexed matching across Python 3.10–3.13

The follow-up to
[`7ccb167`](https://github.com/weiliddat/mgqpy/commit/7ccb167fe2f3857aeda3cf6df21537b14af24a32)
adds the seven workloads missing from the original baseline. Measured on the same
orb on 2026-10-17, using CPython 3.10.21, 3.11.6, 3.12.14, and 3.13.15. Within
each interpreter, 0.9.0, the reviewed base, and the corrected base were imported
as independent module trees, with source paths and matcher identities checked.
Construction was outside timing; every predicate was checked against the expected
result and warmed with 100 calls. `timeit` disabled GC. Each workload used the
same iteration count for all variants, calibrated from 100 calls of the slowest
variant to target 20 ms per block (minimum 20 iterations). The 20 blocks shuffled
variant order with `random.Random(4361)`; values below are medians of per-call
block timings, including identical lambda overhead. Interpreters ran serially.

The new workloads on **Python 3.11**, in microseconds:

| Matching | 0.9.0 | Reviewed base | Corrected base |
| --- | ---: | ---: | ---: |
| Indexed equality (`a.9.x`) | 2.010 | 2.049 | 1.869 |
| Two-digit index (`a.73.x`) | 2.099 | 2.073 | 1.892 |
| `$size` | 1.738 | 1.972 | 1.036 |
| Deep `$size` | 3.471 | 4.508 | 1.828 |
| `$mod` | 2.633 | 5.078 | 1.630 |
| Deep `$mod` | 5.168 | 12.046 | 2.471 |
| Array `$mod` | 91.998 | 238.556 | 60.577 |

Ratios of **corrected base / 0.9.0** for every matching workload; lower is faster:

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | ---: | ---: | ---: | ---: |
| Flat equality | 0.866× | 0.894× | 0.997× | 1.004× |
| Deep dict path | 0.809× | 0.854× | 0.981× | 0.969× |
| Arrays of subdocuments | 0.893× | 0.894× | 0.979× | 0.971× |
| Large `$in` | 0.892× | 0.946× | 0.977× | 0.959× |
| Regex | N/A | 0.614× | 0.574× | 0.581× |
| `$and`/`$or` | 0.912× | 0.929× | 0.920× | 0.919× |
| Indexed equality | 0.873× | 0.930× | 1.005× | 1.002× |
| Two-digit index | 0.898× | 0.901× | 1.013× | 1.011× |
| `$size` | 0.549× | 0.596× | 0.611× | 0.547× |
| Deep `$size` | 0.538× | 0.527× | 0.509× | 0.498× |
| `$mod` | 0.663× | 0.619× | 0.628× | 0.571× |
| Deep `$mod` | 0.545× | 0.478× | 0.473× | 0.454× |
| Array `$mod` | 0.718× | 0.658× | 0.655× | 0.667× |

0.9.0's explicit regex workload raises `AttributeError` on Python 3.10 because
`re.NOFLAG` is unavailable, so that baseline cannot be timed. The corrected base
matches successfully at 1.812 µs there. Indexed matching is faster on 3.10/3.11
and within 1.3% of 0.9.0 on 3.12/3.13; these shared-orb observations do not establish
an exact zero-overhead guarantee. All other matching medians are faster or within
0.4% of 0.9.0. Numeric workloads are 28–55% faster than 0.9.0 across interpreters.

`$mod` and `$size` validate and normalize their query operands only at construction;
matching retains the checks on document values. Equality now distinguishes a
prepared regex (original literal plus ASCII matcher) from an explicit literal
regex, so it needs no recursive regex-mode flag. It also uses a direct empty-path
check and no longer rechecks validated query key types. The canonical index helper
has a bounded 128-entry cache of boolean results for repeated path segments.
This comparison retained eager array evaluation; no path cache or new traversal
representation was introduced.

The expanded pytest-benchmark suite passes all 26 matching/construction cases.
A separate short run on Python 3.11 measured construction at 207 µs for large
`$in`, 4.917 µs for `$mod`, 2.585 µs for `$size`, and 3.477 µs for regex, using
`--benchmark-min-rounds=5 --benchmark-max-time=0.1 --benchmark-disable-gc`.
The snapshot copier is unchanged.

## Short-circuit evaluation: strategy comparison and final baseline

The final [evaluation contract](../README.md#evaluation-contract) propagates
reached errors and stops when an operator's result is decided. Rerun on the same
orb and four interpreters, with the same 20-block interleaved methodology above.
Three independent imports of the final source compared only the array/logical
aggregation approach: eager result-list loops, generators with `any()`/`all()`,
and early-return loops. A temporary AST import loader replaced the 25 simple
early-return loops in matchers with the other two forms; construction, numeric
preparation, comparison guards, and the early-return condition dispatcher were
identical. The original 0.9.0 source was imported separately as a fourth variant.
Every timed predicate returned the expected result before measurement.

**Python 3.11 medians, in microseconds:**

| Matching | 0.9.0 | Eager loops | Generators | Early-return loops |
| --- | ---: | ---: | ---: | ---: |
| Flat equality | 1.405 | 1.147 | 1.216 | 1.152 |
| Deep dict path | 2.310 | 1.805 | 2.029 | 1.804 |
| Arrays of subdocuments | 93.394 | 82.694 | 67.479 | 58.964 |
| Large `$in` | 668.589 | 615.684 | 657.216 | 618.541 |
| Regex | 2.258 | 1.149 | 1.218 | 1.161 |
| `$and`/`$or` | 6.891 | 4.715 | 6.053 | 4.651 |
| Indexed equality | 2.056 | 1.747 | 1.920 | 1.747 |
| Two-digit index | 2.082 | 1.766 | 1.925 | 1.742 |
| `$size` | 1.821 | 0.903 | 0.973 | 0.897 |
| Deep `$size` | 3.604 | 1.556 | 1.840 | 1.562 |
| `$mod` | 2.668 | 1.458 | 1.529 | 1.458 |
| Deep `$mod` | 5.268 | 2.203 | 2.379 | 2.176 |
| Array `$mod`, second value matches | 94.181 | 56.802 | 3.082 | 2.169 |
| Array `$mod`, 100th value matches | 93.362 | 54.351 | 62.666 | 51.947 |

Early-return loops avoid generator/frame and result-list overhead. On scalar
workloads they are essentially tied with eager loops; generators add closure
overhead even on calls that never enter an array. Eager evaluation is also
incompatible with the new short-circuit contract. The array `$mod` early-match
speedup is mostly skipped work; the last-element control shows the full-scan
improvement separately. Large `$in` matches its final (1,000th) operand.

Ratios of **final early-return loops / 0.9.0**, lower is faster:

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | ---: | ---: | ---: | ---: |
| Flat equality | 0.797× | 0.820× | 0.897× | 0.910× |
| Deep dict path | 0.807× | 0.781× | 0.928× | 0.912× |
| Arrays of subdocuments | 0.616× | 0.631× | 0.688× | 0.704× |
| Large `$in` | 0.882× | 0.925× | 0.986× | 0.971× |
| Regex | N/A | 0.514× | 0.535× | 0.552× |
| `$and`/`$or` | 0.754× | 0.675× | 0.694× | 0.754× |
| Indexed equality | 0.846× | 0.850× | 0.938× | 0.944× |
| Two-digit index | 0.866× | 0.837× | 0.963× | 0.949× |
| `$size` | 0.508× | 0.492× | 0.543× | 0.471× |
| Deep `$size` | 0.479× | 0.434× | 0.457× | 0.469× |
| `$mod` | 0.617× | 0.546× | 0.577× | 0.547× |
| Deep `$mod` | 0.505× | 0.413× | 0.446× | 0.437× |
| Array `$mod`, early match | 0.028× | 0.023× | 0.026× | 0.025× |
| Array `$mod`, last match | 0.641× | 0.556× | 0.621× | 0.670× |

No measured matching regression against 0.9.0 in these 14 workloads on any
interpreter. They did not cover the mixed-numeric ranges measured below. The Python
3.10 regex baseline still fails with `re.NOFLAG`; the final source matches at
1.537 µs. These are shared-orb medians, not universal guarantees or CI thresholds.
The final opt-in suite passes all 28 cases. A short Python 3.11 run with the same
pytest-benchmark flags as above measured construction at 206.312 µs for large
`$in`, 4.481 µs for `$mod`, 2.523 µs for `$size`, and 3.318 µs for regex.
Construction and the snapshot copier are unchanged by the evaluation-policy fix.

## Mixed-numeric range matching

The type-bracket guard in
[`418e24f`](https://github.com/weiliddat/mgqpy/commit/418e24f5f5ed7b3b505d77b6ef44d2b9bf0c2012)
uses `numbers.Number` ABC checks for mixed built-in `int`/`float` pairs. Calling
that guard and `coerce()` on every array element regressed against 0.9.0. Each
range matcher now compares exact built-in numeric pairs directly, before the
generic leaf handling. It does not cast either value, preserving integer precision.
Bool, numeric subclasses, Decimal, and other types retain the generic fallback,
including coercion and original exception propagation. Traversal is unchanged.

Measured on the same orb on 2026-10-17 with Python 3.10.21, 3.11.6, 3.12.14,
and 3.13.15, run serially. Independent imports loaded 0.9.0, the reviewed commit,
and the fixed source. The comparison included all 46 committed matching cases,
eight same-type numeric scalar controls, and a deep mixed-numeric path control.
Each predicate was constructed outside timing, checked against its expected
boolean result, and warmed with 200 calls. `timeit` disabled GC. All three
variants used the same iteration count per workload, calibrated from 200 calls
of the slowest variant to target 20 ms per block, bounded to 100–100,000 iterations.
The 24 interleaved blocks shuffled variant order with `random.Random(4361)`.
Values below are medians in microseconds per `test()`, including identical lambda
overhead. These remain shared-orb observations, not universal guarantees.

Exact reproducer: `Query({"x": {"$gt": 72}})` against
`{"x": [0.0] * 99 + [73.0]}` (last match) and `{"x": [0.0] * 100}` (all miss):

| Python | Last: 0.9.0 | Last: reviewed | Last: fixed | Miss: 0.9.0 | Miss: reviewed | Miss: fixed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3.10 | 95.943 | 152.871 | 20.238 | 96.718 | 152.205 | 22.250 |
| 3.11 | 75.978 | 114.669 | 16.391 | 77.297 | 117.462 | 17.590 |
| 3.12 | 66.114 | 105.737 | 13.209 | 67.167 | 107.287 | 14.449 |
| 3.13 | 72.858 | 112.066 | 12.669 | 74.657 | 113.489 | 14.107 |

The same query against scalar `{"x": 73.0}`:

| Python | 0.9.0 | Reviewed | Fixed |
| --- | ---: | ---: | ---: |
| 3.10 | 2.652 | 3.057 | 1.292 |
| 3.11 | 2.031 | 2.147 | 0.998 |
| 3.12 | 1.710 | 1.939 | 0.889 |
| 3.13 | 1.828 | 1.940 | 0.812 |

Ratios of **fixed / 0.9.0** across all four range operators and both numeric
directions; each cell gives the minimum–maximum of eight workloads:

| Workload | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | ---: | ---: | ---: | ---: |
| Scalar match | 0.480–0.500× | 0.491–0.503× | 0.508–0.524× | 0.443–0.459× |
| Scalar miss | 0.407–0.436× | 0.409–0.448× | 0.423–0.469× | 0.371–0.394× |
| Array last match | 0.211–0.218× | 0.216–0.227× | 0.196–0.214× | 0.173–0.184× |
| Array all miss | 0.226–0.230× | 0.228–0.241× | 0.213–0.223× | 0.187–0.196× |

No measured regression against 0.9.0 in any of the 55 matching cases on any
interpreter where the baseline runs. The 14 original workloads were also
rechecked; their worst fixed/baseline ratios were 0.851×, 0.907×, 0.960×, and
0.969× on Python 3.10, 3.11, 3.12, and 3.13 respectively. 0.9.0's explicit regex
still fails on Python 3.10 (`re.NOFLAG`); that single baseline is not timed.
The expanded opt-in suite passes all 60 matching/construction cases.

## Shared compiled traversal

The path branch compiles field predicates and paths at construction and shares
one walker across operators. Remeasured on the same orb, against independent
imports of 0.9.0 and the exact
[`v1-base` snapshot](https://github.com/weiliddat/mgqpy/commit/ff986702adf4bb65c22ccd58a00be5f12c5a8d1d).
The method is the 24-block interleaved comparison described above: 200 warmup
calls, GC disabled, identical calibrated counts targeting 20 ms per block,
100–100,000 iterations, shuffled by `random.Random(4361)`. Python versions run
serially. Every predicate is checked before timing; old versions giving a wrong
answer or raising are excluded from that case, not counted as speedups.

Worst matching ratio across the **55 existing matching workloads and controls**
(lower is faster; no averaging of regressions into unrelated improvements):

| Python | Paths / 0.9.0 | Paths / v1-base |
| --- | ---: | ---: |
| 3.10.21 | 0.515× | 0.862× |
| 3.11.6 | 0.483× | 0.888× |
| 3.12.14 | 0.518× | 0.875× |
| 3.13.15 | 0.515× | 0.882× |

0.9.0's Python 3.10 explicit regex still raises, leaving 54 comparable cases
there. Numeric equality avoids native coercion when both values are exact
built-in numbers; integer precision and the base's equality semantics remain
unchanged. Compilation removes the matching-time expression dispatcher, path
splits, slices and index classification. Python 3.11 medians are 0.515 µs (flat),
0.937 µs (deep), 25.359 µs (subdocuments), 110.949 µs (large `$in`), 0.682 µs
(regex), and 1.621 µs (logical composition). These are shared-orb observations,
not universal performance guarantees.

The opt-in suite now has 85 cases. New cases cover early/last/missing matches
through 100 subdocuments for equality, membership, existence, size, all and
elemMatch, plus numeric-field alternatives, indexed misses, scalar-array/null
and nested-leaf controls. Correct indexed misses now search literal numeric
fields in every immediate subdocument: `x.73.y` against 100 `{"y": 0}` objects
takes 22.798 µs on Python 3.11 versus 1.870 µs in the base. This is necessary
additional work, absent from the old indexed-hit benchmarks; successful indexed
matching still returns before searching alternatives. The new last-hit existence
case can also cost more than the old dedicated existence walker. These costs
are reported separately from the existing-workload gate.

These results include the review fix that normalizes the final result with
`bool()` in `Query.test()`, rather than individual leaf matchers. Custom Python
comparisons can return non-booleans, so the public contract needs this boundary.
Pickle reconstruction recompiles the private query snapshot; it adds no work to
matching and preserves process-pool use.

Empty `$all` compiles to a constant false at its operator position. The positive
and negated 100-subdocument controls take 0.158/0.199 µs on Python 3.11, versus
0.813/1.615 µs in `v1-base`, using the same interleaved method. No path lookup or
iteration is needed; earlier operators and construction-time validation remain
unchanged. Both controls are faster than either baseline on all four interpreters.

Construction remains separately measured by `test_construct`; compilation
intentionally moves work out of repeated matching. Correctness and installed-
wheel checks run separately from these CPU-only measurements.

## Shared value comparison

Shared equality and BSON ordering apply pairwise native conversion recursively.
Range matching reuses converted, classified pairs instead of preparing them
again. Exact built-in numbers keep direct range entries; successful date/UUID
conversion uses same-type equality without repeating generic classification.

`$all` walks a path once and replays reached leaves for later requirements.
Requirements stay ordered, and a deciding match does not force the remaining
path. Exact built-in numeric/string arrays use C-level membership after checking
bounded prefixes, not the entire unread tail. Bools, NaN operands, native values,
regexes and containers use shared equality. Certification lives only within one
evaluation; mutable documents are never cached between calls.

### Four-interpreter gate

Measured on 2026-10-17 in the same orb, comparing independent imports of
[0.9.0](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d),
[v1-base](https://github.com/weiliddat/mgqpy/commit/ff986702adf4bb65c22ccd58a00be5f12c5a8d1d)
and the value branch. Source paths and function globals were checked. Each
predicate had to return the expected boolean before timing; incorrect or raising
old versions were excluded rather than reported as speedups. Construction was
outside timing. Each case used 200 warmup calls and 24 shuffled/interleaved
`timeit` blocks, GC disabled, with `random.Random(4361)`. Equal iteration counts
targeted 20 ms per block, bounded to 100–100,000 calls. Interpreters ran serially.

The gate covers 132 matching cases from `test_benchmarks.py` plus the nine numeric
range controls above. The opt-in suite separately passes 154 matching/construction
cases. Added controls include early/last/missing document equality, all four
document/binary ranges with 100-value last-hit and all-miss arrays, date/UUID
last-hit and all-miss arrays, and numeric/string `$all` prefix hits in 10,000- and
100,000-value arrays, including shifted prefixes and reversed requirements.

The gate excludes traversal costs inherited from `v1-paths` (late/missing `$size`
and `$exists`, and indexed misses), which `v1-values` does not change. For example,
Python 3.11 indexed misses take 2.277 → 23.307 µs because numeric-field alternatives
require scanning subdocuments; [Shared compiled traversal](#shared-compiled-traversal)
explains why.

The original 55-workload subset remains faster than both baselines. In the
expanded gate, comparison/native controls also meet `v1-base`, with two accepted
exceptions: ordered-document equality and sub-microsecond `$all` overhead.

| Python | Original: new / 0.9.0 | Original: new / base | Expanded controls: new / base | Largest $all overhead |
| --- | ---: | ---: | ---: | ---: |
| 3.10.21 | 0.529× | 0.832× | 0.985× | 0.979 µs |
| 3.11.6 | 0.492× | 0.877× | 0.922× | 0.553 µs |
| 3.12.14 | 0.536× | 0.894× | 0.976× | 0.290 µs |
| 3.13.15 | 0.514× | 0.887× | 0.987× | 0.931 µs |

Ratios are the worst comparable median in each group; expanded-control ratios
exclude the two exceptions and inherited traversal costs. 0.9.0's Python 3.10
explicit regex raises, leaving 54 comparable original cases there. One Python
3.12 document `$gte` last-hit observation was 0.5% slower than base. A focused
repeat of all eight document-range controls, with 32 interleaved 50 ms blocks,
measured every control faster without a code change (`$gte`: 55.603 → 50.362 µs);
the expanded-control ratio uses that repeat. These shared-orb medians are not
universal performance guarantees or CI thresholds.

### Prefix matching stays bounded; full scans remain controls

Python 3.11 medians, microseconds per evaluation:

| Matching | v1-base | Values |
| --- | ---: | ---: |
| Numeric $all, first two of 10,000 | 2.290 | 2.038 |
| Numeric $all, first two of 100,000 | 2.275 | 2.049 |
| String $all, first two of 10,000 | 2.245 | 2.067 |
| String $all, first two of 100,000 | 2.271 | 2.115 |
| Document $gt, last of 100 | 62.067 | 56.270 |
| Binary $gt, last of 100 | 88.040 | 48.677 |
| Date/string equality, last of 100 | 66.622 | 46.678 |
| Date/string equality, all miss | 66.539 | 46.483 |
| UUID/string equality, last of 100 | 198.083 | 150.079 |
| UUID/string equality, all miss | 200.851 | 152.368 |
| Ordered document equality, last of 100 | 74.950 | 113.048 |
| Ordered document equality, all miss | 75.715 | 114.088 |
| Native document equality, all miss | 106.724 | 197.267 |

Recursive document equality intentionally replaces Python's C-level dict
equality: it checks key order, bool/number separation, NaNs and native scalar
pairs within containers. Last-hit document equality costs about 1.5–1.6× base
across interpreters; the native-document miss costs about 1.8–2.2×. Small `$all`
cases retain the sub-microsecond overhead above, but large prefix hits no longer
scale with the unread array length. Native-container hits that old versions
reject have no comparable baseline timing. Construction remains measured
separately; reuse queries when matching many documents.

## Value-form elemMatch and empty path suffixes

The operator branch adds raw-element `$elemMatch`, array-boundary handling of a
final empty path component, and selective singleton `$all` lowering.
The suite now has 169 matching and 25 construction cases (194 total). New controls
cover early/last/missing singleton `$all` for numbers, strings, regexes, documents,
arrays and dates; raw-value, nested and `$all` value-form `$elemMatch`; outer `$all`
with both forms, separately and mixed; and empty suffixes with equality, `$size`,
`$all` and indexing.

Unconditional singleton lowering was rejected. A preliminary Python 3.11 run
changed numeric last-hit matching from 3.47 to 9.90 µs and a string miss from 3.64
to 14.40 µs: ordinary equality loses the existing C-level membership fast path.
Exact `int`/`float`/`str` requirements therefore retain that path. Other singleton
requirements lower to their equality, regex or `$elemMatch` child. Direct-value
`$all` compiles each requirement against the same raw element, regardless of
operand type; it must not expand the element as an ordinary field matcher would.

The comparison uses the exact
[`v1-values` snapshot](https://github.com/weiliddat/mgqpy/commit/6e1bed77e050ac455a2774eeffd6a2f9bacd5c33).
All 132 existing matching workloads are included, including the inherited traversal
controls previously excluded when comparing the value branch with `v1-base`.
Another 20 new controls have correct baseline results, giving 152 comparable
cases. Baseline rejection or wrong answers on the 17 newly supported cases are
reported separately, not counted as speedups. Each source tree is imported with
independent globals, and source paths, shared equality and regex identities are
checked. Matching uses 200 warmup calls and 24 shuffled/interleaved `timeit` blocks,
GC disabled, equal calibrated counts targeting 10 ms of process CPU time per block
(100–100,000 calls), and `random.Random(4361)`. Interpreters run serially;
construction stays outside the timed region. Ratios use the median of paired
new/baseline block times, reducing correlated host-load effects.

Cases initially more than 1% slower were rechecked in six fresh processes per
interpreter, pinned to one vCPU, alternating import order, with 16 paired 10 ms
blocks. Each case's rechecked ratio is the median of its six process ratios;
unselected cases retain their initial result. Identical-source controls use two
fresh processes with the same settings. These controls measure timing variation,
not a correction factor applied to the results.

| Python | Largest comparable new / values ratio | Identical-source ratio range |
| --- | ---: | ---: |
| 3.10.21 | 1.011× | 0.972–1.025× |
| 3.11.6 | 1.019× | 0.985–1.027× |
| 3.12.14 | 1.014× | 0.952–1.042× |
| 3.13.15 | 1.019× | 0.983–1.037× |

No slowdown exceeds the identical-source variation in this run, but these
measurements do **not** establish a strict zero-regression gate: residual slower
medians remain, up to 1.9%. In particular, Python 3.11's early document-form
`$elemMatch` measured 1.0–2.3% slower across all six repeats. Its runtime call graph
is unchanged; the empty-suffix check adds work only when traversal reaches an
array with an unconsumed path. Treat small differences as unresolved, rather than
claiming every workload is faster.

Representative Python 3.11 medians, microseconds per evaluation:

| Matching | v1-values | Operators |
| --- | ---: | ---: |
| Singleton regex `$all`, first of 100 | 1.027 | 0.739 |
| Singleton array `$all`, first of 100 | 1.413 | 1.048 |
| Singleton array `$all`, last of 100 | 65.949 | 58.434 |
| Singleton document `$all`, last of 100 | 117.813 | 110.382 |
| Singleton numeric `$all`, last of 100 | 3.394 | 3.404 |
| Singleton string `$all`, all miss | 3.465 | 3.473 |

Across all four interpreters, singleton regex prefix hits improve 26–32%, array
prefix hits 25–31%, array full scans 10–17%, and document full scans 6–8%.
All 194 benchmark cases pass on each interpreter. The baseline rejects value-form
`$elemMatch` and gives incorrect empty-suffix answers, so their new timings have
no valid speed ratio against it.
