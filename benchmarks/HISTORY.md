# Historical performance measurements

These are the previously recorded measurements, not results of the versioned
harness. Dates, source revisions, suite counts and methods refer to the historical
checkouts. Temporary audit runners were not committed; their recovered workloads
now live in `cases.py`. Use [README.md](README.md) for current commands and the
current 0.9.0/1.0.1/1.0.2 snapshot. Historical timings are shared-orb observations, not
performance guarantees or thresholds.

## 0.9.0 versus the 1.0 stack

Matching-time ratios, **1.0 / 0.9.0**; lower is faster. Full scans use 100 array
members unless noted. This final-stack measurement comes before the historical
branch-by-branch measurements below; those earlier results do not cover every
cost in the finished comparison model.

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | ---: | ---: | ---: | ---: |
| Flat equality | 0.35× | 0.31× | 0.34× | 0.31× |
| Deep dict path | 0.34× | 0.34× | 0.38× | 0.41× |
| Mixed numeric range, last hit | 0.13× | 0.13× | 0.12× | 0.10× |
| `$in`, last of 1,000 | 0.27× | 0.21× | 0.22× | 0.20× |
| Numeric `$all`, late hit | 0.89× | 0.98× | 0.87× | 1.04× |
| Ordered-document equality, last hit | 1.54× | 1.43× | 1.43× | 1.42× |
| Numeric-index miss | 8.40× | 7.24× | 9.43× | 8.86× |
| Singleton `$all` over documents, last hit | 19.05× | 12.33× | 13.62× | 18.12× |
| Singleton `$all` over arrays, last hit | 15.82× | 9.30× | 12.11× | 16.04× |

All-miss scans are similar: ordered-document equality is 1.40–1.53×,
singleton document `$all` 12.17–19.14×, and singleton array `$all` 9.41–16.27×.

Measured on 2026-10-18 in a shared Linux x86-64 Amp orb, Intel Xeon 2.60 GHz,
CPython 3.10.21/3.11.6/3.12.14/3.13.15. The source snapshots are
[0.9.0](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d)
and the [1.0 candidate](https://github.com/weiliddat/mgqpy/commit/137f01c3d465d6f70ab704241fd02457f706094d),
whose runtime source equals the `v1-operators` baseline. The polish gate below
checks subsequent changes against that baseline separately.

The whole-stack audit measured 240 scenarios per interpreter, matching and
construction separately. Two fresh processes reversed independent-source import
order, each using 100 warmups and 12 shuffled paired blocks targeting 5 ms of
process CPU time, pinned to CPU 0, with GC disabled during timing. The table uses
the median of all 24 paired ratios, not a selected favorable process. Wrong,
rejected or crashing 0.9.0 results have no speedup ratio; its explicit regex also
fails on Python 3.10. Identical-source variation reached about 5.1%, so numeric
`$all` is near parity, not a reliable speedup. These are observations, not guarantees.

Document equality checks key order and compares values recursively instead of
using Python's C-level dict equality; singleton container `$all` also replaces
C-level membership. Numeric-index misses search literal numeric-field alternatives
that 0.9.0 skipped. The costs do not amortize away by reusing a query on these workloads.

Construction is the up-front cost: flat `Query` construction rose from
0.073–0.158 µs to 1.840–2.932 µs; matching fell from 0.952–1.676 µs to
0.297–0.582 µs. Flat equality breaks even after three documents in this run.
That is not a universal break-even point. Reuse `Query` objects, and measure the
queries and document shapes your application actually uses.

## v1-polish versus v1-operators

The incremental gate compares the polish changes with
[`v1-operators`](https://github.com/weiliddat/mgqpy/commit/b6f91534fce84a49a47faa8f7016b8809f7ea229),
not with 0.9.0. It covers 254 comparable matching cases: 184 existing fixtures,
56 broader audit controls and 14 added numeric-guard controls. All answers agree.
Construction is measured separately for the 25 existing construction fixtures.

On the same orb and four interpreters above, two fresh processes use 100 warmups
and 12 shuffled paired 5 ms CPU-time blocks, pinned to CPU 0 with GC disabled.
Every initial ratio over 1.01, all construction fixtures, all `$mod` controls,
the nine indexed-list controls and selected early-path/array controls receive
six fresh-process 16-block rechecks (81–85 cases per interpreter). Two further
processes compare independent identical-source imports. Import order alternates.
Rechecked cases pool all 96 paired ratios; other cases retain their initial 24.

| Python | Largest matching ratio | Identical-source matching range | Construction ratio range |
| --- | ---: | ---: | ---: |
| 3.10.21 | 1.011× | 0.982–1.033× | 0.991–1.003× |
| 3.11.6 | 1.014× | 0.970–1.023× | 0.983–1.006× |
| 3.12.14 | 1.013× | 0.986–1.018× | 0.986–1.009× |
| 3.13.15 | 1.011× | 0.987–1.033× | 0.991–1.006× |

No incremental regression stands out from the observed timing variation; this
does not establish exact zero overhead. The `$mod` controls are at most 1.008×.
Named ranks define `_KINDS`; annotated hot-path literals preserve the executable
bytecode of all 15 comparison functions on each interpreter. `$all` replay and
chunked membership are unchanged.

Two additional sNaN cases measure new behavior, not speedups: scalar rejection
takes 1.13–1.91 µs and rejecting 100 members takes 79.8–112.8 µs across the four
interpreters. The baseline raises `ValueError` instead of returning a boolean.
The 225 benchmark cases pass on every interpreter. All eight Python × MongoDB
7/8 runs pass 800 correctness tests with 100% line coverage; four isolated wheel
smokes pass without runtime dependencies. Generated tests compare 25,787 fast
and general-path outcomes. A fresh differential checks 4,974 queries × 415
documents per server: 4,850 accepted queries agree, 124 are rejected by both,
and there are zero mismatches on MongoDB 7.0.45 and 8.0.34.

## 0.9.0 versus the initial v1 base

Measured on 2026-10-17 in the same Linux x86-64 Amp orb, CPython 3.11.6,
pytest-benchmark 5.2.3, Intel Xeon @ 2.60 GHz. Values are medians in microseconds
per invocation; lower is faster. Baseline source is
[0.9.0 on main](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d).
Both versions ran the same cases and interpreter sequentially, with at least 30
rounds, a 0.5-second maximum per benchmark, warmups on and GC disabled.
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
The suite now has 184 matching and 25 construction cases (209 total). New controls
cover early/last/missing singleton `$all` for numbers, strings, regexes, documents,
arrays and dates; raw-value, nested and `$all` value-form `$elemMatch`; outer `$all`
with both forms, separately and mixed; and empty suffixes with equality, `$size`,
`$all` and indexing. Six controls cover early/last/missing `$size` and `$elemMatch`
over the candidate stream added by an indexed empty suffix. Nine more keep
ordinary indexed lists explicit: scalar/field/array-operator hits, a terminal
index, and nested indexing at depths 4, 8 and 16.

Unconditional singleton lowering was rejected. A preliminary Python 3.11 run
changed numeric last-hit matching from 3.47 to 9.90 µs and a string miss from 3.64
to 14.40 µs: ordinary equality loses the existing C-level membership fast path.
Exact `int`/`float`/`str` requirements therefore retain that path. Other singleton
requirements lower to their equality, regex or `$elemMatch` child. Direct-value
`$all` compiles each requirement against the same raw element, regardless of
operand type; it must not expand the element as an ordinary field matcher would.

The initial 169-case matching comparison uses the exact
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

The residual 1–2% on early document-form `$elemMatch` is an accepted
measurement-noise exception. It measured 1.0–2.3% slower across six repeats here;
an independent check reproduced 1.011× while identical-source controls reached
1.018× on that same workload. Python 3.10's outer `$all` of value-form `$elemMatch`
is also an accepted noise exception: its six-process median was 1.016×, within
the independently measured identical-source variation. These exceptions do not
exempt other matching workloads from the performance gate. The final bound-walker
measurements below supersede these intermediate results.

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
The initial 194 benchmark cases pass on each interpreter. The baseline rejects
value-form `$elemMatch` and gives incorrect empty-suffix answers, so their new
timings have no valid speed ratio against it.

### Indexed empty-suffix correction

The correction compares all 169 existing matching workloads with the reviewed
[`v1-operators` snapshot](https://github.com/weiliddat/mgqpy/commit/c6a12cc6eed9c1bb2216361ef6adb385998b9ff7).
It uses the paired CPU-time method above, pinned to one vCPU: 500 warmup calls,
24 shuffled 10 ms blocks, then six fresh-process 16-block rechecks for cases
initially over 1% slower and the indexed/early-elemMatch controls. Rechecks
alternate import order. Two identical-source processes use the same settings.
Each rechecked ratio is the median of six process ratios; other cases retain
their initial ratio. No implementation is substituted during timing.

| Python | Indexed dict hits: worst new / previous | Indexed empty-suffix equality | Largest existing-control ratio | Identical-source range |
| --- | ---: | ---: | ---: | ---: |
| 3.10.21 | 0.978× | 0.972× | 1.016× | 0.967–1.015× |
| 3.11.6 | 0.986× | 0.940× | 1.012× | 0.979–1.015× |
| 3.12.14 | 0.969× | 0.919× | 1.015× | 0.962–1.031× |
| 3.13.15 | 0.971× | 0.920× | 1.016× | 0.962–1.012× |

That intermediate correction split dictionary and array selection, keeping the
suffix check off ordinary indexed-document traversal. Indexed dict hits improved
1–3%, and indexed empty-suffix equality improves 3–8%. Other controls retain small
positive differences, at most 1.7%, while identical-source runs deviate by up to
3.8%. These observations do not establish exact zero overhead. In particular,
Python 3.10's outer `$all` of value-form `$elemMatch` measured 1.006–1.028× across
all six repeats (median 1.016×); this is the accepted noise exception recorded
alongside the early document-form case above.

The six added indexed-empty-suffix controls measure newly required candidate
work, separately from those 169 existing workloads. Four hits were incorrectly
rejected before the fix. The two misses also inspect previously skipped immediate
members now, even though their final boolean is unchanged. Python 3.11 medians
in microseconds for 100 immediate members:

| Matching | First hit | Last hit | All miss | Previous all miss |
| --- | ---: | ---: | ---: | ---: |
| `$size: 0` | 0.777 | 7.103 | 7.269 | 0.862 |
| `$elemMatch: {$eq: 1}` | 0.937 | 20.596 | 68.970 | 49.930 |

These rare-path full scans cost more because they now test every required
candidate; they are not counted as matching speedups or unchanged-work controls.
The focused real-server differential covers 924 queries × 382 documents per
MongoDB version: 67 mismatching queries before the fix, zero afterward on both
7.0.45 and 8.0.34. All 200 benchmark cases pass on Python 3.10–3.13.

### Final ordinary-path gate

Field predicates now bind the path length and final-empty classification at
construction. One module-level walker keeps recursive calls out of per-field
closures; the binding also removes the compiler's matching-time wrapper. Ordinary
paths test a cached false flag instead of inspecting suffixes. `$all` binds the
same walker and supplies fresh replay state on each invocation. Its compiler
groups empty, raw-element, singleton and fallback cases under one `$all` branch.

Remeasured on 2026-10-18 with the same independent-source, paired CPU-time method:
200 warmups, 24 shuffled 10 ms blocks, construction outside timing, GC disabled,
and equal calibrated iteration counts. All 184 matching cases run. The gate has
161 comparable unchanged-work controls against the `v1-values` snapshot above:
all 132 existing cases, 20 other controls and the nine explicit indexed-list
controls. It includes late/missing `$size` and `$exists` and indexed misses; none
are excluded as inherited costs when comparing with `v1-values` itself.

The other 23 cases either have incorrect/rejected baseline results or require
new candidate work. They are measured against the reviewed
[`v1-operators` snapshot](https://github.com/weiliddat/mgqpy/commit/9d3f6d84be2bdd81b059a6bfe70ae82bb70c65f8),
which already has the same candidate semantics. Neither group counts incorrect
baseline answers as speedups. Cases initially over 1% slower get six fresh-process
16-block rechecks, alternating import order; all nine indexed-list controls and
early `$size`, `$exists` and document-form `$elemMatch` are also rechecked. Two
identical-source processes measure variation separately. Rechecked ratios are
medians of the six process ratios, not averages across workloads.

| Python | 161 controls / values: worst | Nine indexed-list controls: worst | 23 new-semantics controls / reviewed operators: worst | Identical-source range (values) |
| --- | ---: | ---: | ---: | ---: |
| 3.10.21 | 1.014× | 0.956× | 1.000× | 0.961–1.037× |
| 3.11.6 | 1.010× | 0.988× | 1.009× | 0.957–1.029× |
| 3.12.14 | 1.009× | 0.989× | 1.008× | 0.989–1.027× |
| 3.13.15 | 1.010× | 0.987× | 1.005× | 0.969–1.004× |

No existing workload regresses beyond the observed timing variation. The largest
positive observation is 1.4% on Python 3.10 document-equality misses; identical-
source observations deviate by up to 4.3% in either direction. These are shared-
orb measurements, not an exact zero-overhead guarantee. The formerly regressing
indexed-list and early path controls are faster on every interpreter.

Python 3.11 medians across the six process medians, microseconds per evaluation:

| Matching | v1-values | Operators |
| --- | ---: | ---: |
| `x.0.0` over `[[1]]` | 0.834 | 0.770 |
| `x.0.y` over `[[{"y": 1}]]` | 1.047 | 0.999 |
| Indexed lists, depth 16 | 4.142 | 3.883 |
| Early path `$size` | 0.725 | 0.693 |
| Early path `$exists` | 0.685 | 0.646 |

The accepted early document-form and outer-value-form noise exceptions remain
recorded above. In this final run, early document-form `$elemMatch` is 7–14%
faster than `v1-values`; Python 3.10 outer `$all` of value-form `$elemMatch` is
0.986× the reviewed operator snapshot. Additional indexed-empty candidates still
cost real full-scan work, as reported above. Construction is separate: flat
`Query` construction adds 0.17–0.26 µs versus that reviewed snapshot (Python 3.11:
2.435 → 2.658 µs) to prepare the binding. Reuse queries for repeated matching.

All 209 benchmark cases pass on each interpreter. All eight Python 3.10–3.13 ×
MongoDB 7/8 correctness runs pass 785 tests with 100% line coverage; installed-
wheel smoke checks pass on all four Pythons. A fresh numeric/empty-component
differential checks 700 queries × 145 documents on each server, with zero
mismatches on MongoDB 7.0.45 and 8.0.34.

## Unmerged 1.0.2 candidate: original #21 measurements

These numbers were recorded by the [#21 author](https://github.com/weiliddat/mgqpy/pull/21),
not rerun by the versioned 0.9.0/1.0.1 baseline. The measured candidate was
[`81169c5`](https://github.com/weiliddat/mgqpy/commit/81169c5), with identical runtime
source at the [documented head](https://github.com/weiliddat/mgqpy/commit/042cee515d7877392c56ff463663942d444a4b31).
Its baseline was [1.0.1](https://github.com/weiliddat/mgqpy/commit/8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87).
This is historical evidence about an unmerged candidate, not a released result or
an endorsement of its unchanged-behavior claims.

Ratios are candidate / 1.0.1; the last column compares candidate / 0.9.0 across
four interpreters. Full scans use 100 members.

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | vs 0.9.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Numeric-index miss | 0.25× | 0.28× | 0.26× | 0.29× | 2.06–2.66× |
| `$exists` over subdocuments, last hit | 0.24× | 0.30× | 0.26× | 0.30× | 0.19–0.20× |
| Subdocument field, last hit | 0.84× | 0.84× | 0.84× | 0.85× | 0.25–0.28× |
| Flat-document equality, last hit | 0.40× | 0.39× | 0.38× | 0.37× | 0.35–0.39× |
| Singleton `$all` over flat arrays, last hit | 0.37× | 0.38× | 0.38× | 0.34× | 4.26–5.63× |
| Singleton `$all` over nested documents, last hit | 1.01× | 1.01× | 1.00× | 1.01× | 13.88–18.23× |
| Path `$in` of two, last hit | 0.39× | 0.40× | 0.40× | 0.40× | 0.11–0.12× |

A 1,000-member `$in` last hit took 0.55–1.04 µs instead of 140–233 µs
(0.9.0: 625–1,043 µs). Across the original 258 cases, per-interpreter median
matching ratios were 0.997–1.003×. Initial outliers up to 1.14× on Python 3.10
were followed by selected two-process/16-block rechecks at 0.96–1.02×;
identical-source controls spanned 0.88–1.05×. This did not test every workload
and does not establish zero regressions.

| Construction | 1.0.1 (µs) | Candidate (µs) | Paired ratio |
| --- | ---: | ---: | ---: |
| Flat equality | 2.17–3.53 | 1.39–2.29 | 0.64–0.67× |
| 100-clause `$and` | 222–318 | 145–204 | 0.64–0.68× |
| `$in` of 1,000 | 203–337 | 76–100 | 0.23–0.43× |
| Compiled regex | 10.6–16.3 | 2.7–4.3 | 0.26–0.29× |
| `$regex` string | 5.10–7.73 | 4.07–6.29 | 0.79–0.81× |

The reported construction median was 0.78–0.82×, maximum rounded to 1.01× within
that original case set. Construction remained eager. Measured 2026-10-19 in a
shared Linux x86-64 Amp orb, Intel Xeon 2.60 GHz, CPython
3.10.20/3.11.6/3.12.13/3.13.13: two fresh processes with reversed independent
imports, 100 warmups, 12 shuffled paired 5 ms CPU-time blocks/process, GC disabled
while timing, each interpreter pinned to its own physical core. Ratios pooled
all 24 pairs.

The subsequent review found wide-container early rejection and colliding-integer
construction regressions absent from these tables, plus custom-key result
differences. Those cases are in the new harness. The original statements that no
case was reliably slower and no construction case exceeded 1.01× apply only to
the original measured set, not all supported inputs. The candidate is not part
of this PR's runtime changes or fresh baseline measurements.

## 0.9.0 versus 1.0.1 baseline (superseded)

This was the saved baseline before the [current snapshot](README.md#current-snapshot),
which measures 0.9.0, 1.0.1 and 1.0.2 together.

The full baseline was in [`baseline/`](https://github.com/weiliddat/mgqpy/tree/80321d559cf502c79d0d6d7cefe6dff8153792e4/benchmarks/baseline): one JSON/CSV pair per supported
Python. It compares **0.9.0**
([source](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d))
with **1.0.1**
([source](https://github.com/weiliddat/mgqpy/commit/8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87)),
not the unmerged `v1-performance` branch.

Saved results use [runner b54687b](https://github.com/weiliddat/mgqpy/commit/b54687b0b2c0e2f8d2044cb6cea5f995ae63ff59),
before the timed-predicate guards and per-variant module/input isolation. Both
source refs have no deferred imports and leave the fixtures unchanged in an
untimed reuse audit. The timed operations are unchanged; these numbers are kept.

Reproduce with the defaults above (no release tags currently exist):

```sh
for py in 3.10 3.11 3.12 3.13; do
  uv run --no-project --python "$py" python benchmarks/run.py \
    0.9.0=f22a920babc0a37dd07fbe4dae94632f81d9b79d \
    1.0.1=8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87 \
    --output "/tmp/mgqpy-$py.json"
done
```

Measured 2026-10-19 in a shared Linux x86-64 Amp orb, Intel Xeon @ 2.60 GHz.
Interpreters ran serially, each pinned to logical CPU 0, using the default two
processes × 12 blocks and all three operations. Every 1.0.1 case returned its
expected boolean before and after timing. No selective rechecks replace these
results. Units below are µs per invocation; ratios are **1.0.1 / 0.9.0**, lower
is faster.

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | ---: | ---: | ---: | ---: |
| Flat equality | 0.343× | 0.331× | 0.340× | 0.319× |
| Deep dict path | 0.343× | 0.366× | 0.382× | 0.411× |
| Mixed numeric range, last hit | 0.122× | 0.119× | 0.131× | 0.106× |
| `$in`, last of 1,000 | 0.232× | 0.206× | 0.230× | 0.200× |
| Numeric `$all`, late hit | 0.891× | 0.921× | 0.907× | 1.062× |
| Ordered-document equality, last hit | 1.341× | 1.343× | 1.418× | 1.410× |
| Ordered-document equality, all miss | 1.351× | 1.346× | 1.410× | 1.430× |
| Numeric-index miss | 9.279× | 7.598× | 9.212× | 8.441× |
| Singleton document `$all`, last hit | 17.161× | 13.766× | 14.302× | 18.458× |
| Singleton document `$all`, all miss | 17.545× | 13.669× | 14.845× | 18.757× |
| Singleton array `$all`, last hit | 14.416× | 11.601× | 12.706× | 15.840× |
| Singleton array `$all`, all miss | 14.886× | 11.820× | 12.611× | 15.788× |

The slower cases remain slower on repeated matching; query reuse does not remove
their costs. Numeric-index misses include the literal-field alternatives 0.9
skipped. Ordered containers require typed recursive comparison instead of Python's
C-level equality. Numeric `$all` is not a blanket improvement: the 3.13 observation
is 1.062×. This baseline does not claim exact parity or a universal speedup.

Construction ranges across the four Pythons, deliberately separate from matching:

| Construction | 0.9.0 unchecked reference (µs) | 1.0.1 copy/validate/compile (µs) |
| --- | ---: | ---: |
| Flat equality | 0.113–0.221 | 2.197–3.461 |
| `$in` of 1,000 | 0.188–0.282 | 201–333 |
| `$in` of 10,000 | 0.320–0.414 | 2,001–3,348 |
| 100-clause `$and` | 0.205–0.303 | 220–310 |
| 10,000-clause `$and` | 0.360–0.461 | 25,394–35,993 |
| Compiled regex | 0.146–0.236 | 10.734–16.222 |
| `$regex` string | 0.109–0.215 | 5.122–7.696 |
| `$in`, 3,000 colliding integers | 0.215–0.330 | 598–1,005 |

These constructors have different contracts, not comparable validation costs.
0.9.0's constructor can be timed for `$regex` on 3.10, but its matching raises;
there is no paired speedup ratio for that case.

Actual single-use `Query(q).test(doc)`, ranges across the four Pythons (late-hit
rows only here; all-miss controls remain in the CSV/JSON):

| Single use | 0.9.0 (µs) | 1.0.1 (µs) | Paired ratio range |
| --- | ---: | ---: | ---: |
| Flat equality | 1.340–2.318 | 2.608–4.202 | 1.822–1.993× |
| Mixed numeric range, last hit | 70.0–119.2 | 12.8–20.5 | 0.161–0.194× |
| `$in`, last of 1,000 | 638–1,013 | 349–572 | 0.483–0.571× |
| Numeric `$all`, late hit | 3.366–4.977 | 9.499–14.368 | 2.382–2.937× |
| Ordered-document equality, last hit | 70.4–107.3 | 104.0–153.3 | 1.415–1.475× |
| Numeric-index miss | 1.880–3.240 | 17.820–31.411 | 8.485–9.882× |
| Singleton document `$all`, last hit | 6.434–8.715 | 109.6–157.9 | 14.874–18.545× |
| Singleton array `$all`, last hit | 3.903–5.631 | 60.8–94.4 | 12.200–16.902× |

Absolute ranges and paired-ratio ranges are calculated independently; dividing
range endpoints does not reproduce a paired ratio.

The new review controls have a 1.0.1 baseline too. Representative Python 3.11
matching medians, in µs:

| Case | 1.0.1 |
| --- | ---: |
| Empty dict versus 10,000-field dict | 0.582 |
| Empty list versus 10,000-member list | 1.172 |
| Same-length 10,000-field dict, first value misses | 1.063 |
| Same-length 10,000-member list, first value misses | 1.597 |
| 10,000-field whole document, field hit / missing | 0.491 / 0.326 |

Python 3.11 colliding-integer `$in` construction takes 28.282 / 231.304 / 679.378 µs
at 100 / 1,000 / 3,000 operands. These numbers measure 1.0.1, not #21's hash-set
implementation.

| CPython | Same-answer eligible cases / 310 | Identical-source matching | Construction | Single use |
| --- | ---: | ---: | ---: | ---: |
| 3.10.21 | 252 | 0.840–1.221× | 0.985–1.029× | 0.949–1.169× |
| 3.11.6 | 258 | 0.804–1.197× | 0.981–1.026× | 0.926–1.168× |
| 3.12.14 | 258 | 0.819–1.135× | 0.983–1.037× | 0.933–1.158× |
| 3.13.15 | 258 | 0.772–1.146× | 0.982–1.025× | 0.934–1.208× |

The 58/52 flagged older cases include validation rejection, exceptions and wrong
answers, not 1.0.1 failures. Python 3.10 adds the explicit-regex failures. Exact
per-case statuses are in each CSV/JSON. The wide control ranges above are real
observations, especially on very short fast-version blocks; they are not error
bars or a license to dismiss a particular regression. Small future changes need
nearby-ref comparisons and focused rechecks, not division by these saved medians.

## 1.0.2 review rounds on #21

These are the snapshot and rechecks taken while #21 was reviewed, superseded by the
[current snapshot](README.md#current-snapshot). Their files were removed to keep one
current snapshot and remain on the PR branch.

Results were in [`1.0.2/`](https://github.com/weiliddat/mgqpy/tree/d3caccda33c71eb4100324612a660c1a72ba8cf8/benchmarks/1.0.2), one JSON/CSV pair per supported Python for each run:

- `python-*.json`: **0.9.0** ([source](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d)),
  **1.0.1** ([source](https://github.com/weiliddat/mgqpy/commit/8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87)) and the
  **1.0.2 candidate** ([source](https://github.com/weiliddat/mgqpy/commit/a7f0c83140129c7e9c9bf1c8da4ca61747d986a8)) in one
  default run per interpreter. Two later commits change runtime code (see
  [After the independent review](#after-the-independent-review)); `focused-python-*.json`
  measures them.
- `recheck-python-*.json`: focused rechecks of the 20 case patterns in their
  `config.cases`, chosen from the cases initially above 1.03×.
- `recheck-2-python-*.json`: the same recheck, added later, of the five cases the
  first one missed: `all-singleton-regex-99`, `empty-suffix-indexed-size-None`,
  `array-range-element-miss`, `elem-document-last` and `gt-int-float-array-last`.
- `focused-python-*.json`: 1.0.1, the 1.0.2 candidate above (`before`) and
  [49783b0](https://github.com/weiliddat/mgqpy/commit/49783b0) on every case the two later
  runtime commits can affect; `focused-recheck-python-3.13.json` rechecks two of them.
- `per-fix/`: 1.0.1, the pre-fix candidate and each review-fix commit on the target
  cases, to attribute changes to individual commits.
- `before-fixes/`: the first snapshot, of [73dde31](https://github.com/weiliddat/mgqpy/commit/73dde3176648a2520414c3b61f45b006b86f60c8),
  before the review fixes. It is kept for comparison; the tables below use the
  post-fix run unless a column says otherwise.

The [0.9.0/1.0.1 baseline](#090-versus-101-baseline-superseded) above is unchanged and was
measured on different interpreter patch releases; do not divide across the two.

Measured 2026-10-19/20 with [runner 80321d5](https://github.com/weiliddat/mgqpy/commit/80321d559cf502c79d0d6d7cefe6dff8153792e4)
in a shared Linux x86-64 Amp orb, Intel Xeon @ 2.60 GHz, 8 logical CPUs,
CPython 3.10.20/3.11.6/3.12.13/3.13.13: the same machine and interpreters as the
pre-fix snapshot. Interpreters ran serially, pinned to logical CPU 0, with the
defaults (two processes × 12 blocks, all operations). Rechecks used six processes ×
16 blocks × 10 ms. Every case returned its expected boolean in 1.0.1 and 1.0.2; all
four runs exit 0. Eligible 0.9.0 comparisons: 252 cases on Python 3.10 and 258 on
3.11–3.13.

The **1.0.2 / 1.0.1** ratios below are medians of the 24 paired per-block ratios
from the JSON's raw samples, as in the README.

### Review fixes and their target cases

The pre-fix snapshot found one result difference and two regression families. Each
was fixed in its own commit:

1. [1b29b57](https://github.com/weiliddat/mgqpy/commit/1b29b57): flat-container equality checks length first and applies
   only to containers of at most 16 members; larger ones use `equal()`, which rejects
   at the first mismatch. At 16 members, certify-then-C-equality still costs 0.2–0.4×
   of `equal()` on a full hit; at 32 members it already costs more than `equal()`
   needs to reject a first-member mismatch.
2. [d7a7d09](https://github.com/weiliddat/mgqpy/commit/d7a7d09): the flat-dict path requires exact `str` keys on both sides,
   because `equal()` compares keys with their own `!=`.
3. [2edd026](https://github.com/weiliddat/mgqpy/commit/2edd026): `$in`/`$nin` lists with an int or float of magnitude
   `sys.hash_info.modulus` or more keep the pairwise scan instead of a hash set.
   In lists that also held `str` or `None`, this commit checked only ints;
   [c3a2eb4](https://github.com/weiliddat/mgqpy/commit/c3a2eb4) applies it to floats too.
4. [d3f7c0e](https://github.com/weiliddat/mgqpy/commit/d3f7c0e): compiled paths are cached for exact `str` only.
5. [a7f0c83](https://github.com/weiliddat/mgqpy/commit/a7f0c83): compiled-regex flag masks keep `RegexFlag` inversion, so
   undefined flags behave per interpreter as in 1.0.1.

1.0.2 / 1.0.1, before and after:

| Case | Operation | Before fixes | After, 3.10 | 3.11 | 3.12 | 3.13 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `review-wide-dict-empty-100` | match | 2.890–4.282× | 0.790× | 0.788× | 0.807× | 0.744× |
| `review-wide-dict-empty-1000` | match | 18.826–30.699× | 0.818× | 0.784× | 0.808× | 0.759× |
| `review-wide-dict-empty-10000` | match | 145.858–204.471× | 0.807× | 0.783× | 0.799× | 0.762× |
| `review-wide-list-empty-100` | match | 2.166–2.811× | 0.820× | 0.784× | 0.799× | 0.806× |
| `review-wide-list-empty-1000` | match | 10.223–15.413× | 0.904× | 0.975× | 0.896× | 0.882× |
| `review-wide-list-empty-10000` | match | 82.913–135.894× | 0.920× | 0.989× | 0.893× | 0.865× |
| `review-wide-dict-first-mismatch-100` | match | 1.808–2.368× | 0.998× | 1.008× | 1.000× | 1.006× |
| `review-wide-dict-first-mismatch-1000` | match | 11.464–17.158× | 1.006× | 0.983× | 1.001× | 1.000× |
| `review-wide-dict-first-mismatch-10000` | match | 87.358–124.119× | 1.000× | 0.990× | 1.006× | 0.986× |
| `review-wide-list-first-mismatch-100` | match | 1.555–2.238× | 1.002× | 0.996× | 0.997× | 0.996× |
| `review-wide-list-first-mismatch-1000` | match | 7.105–11.344× | 1.054× | 1.139× | 1.002× | 0.999× |
| `review-wide-list-first-mismatch-10000` | match | 60.922–100.004× | 1.216× | 1.254× | 1.185× | 1.279× |
| `review-in-collisions-100` | construct | 1.939–3.083× | 0.380× | 0.572× | 0.534× | 0.530× |
| `review-in-collisions-1000` | construct | 16.851–27.205× | 0.261× | 0.474× | 0.418× | 0.416× |
| `review-in-collisions-3000` | construct | 49.769–78.650× | 0.244× | 0.462× | 0.397× | 0.405× |
| `review-nin-collisions-100` | construct | 1.930–3.111× | 0.379× | 0.575× | 0.539× | 0.535× |
| `review-nin-collisions-1000` | construct | 17.021–27.106× | 0.260× | 0.470× | 0.417× | 0.419× |
| `review-nin-collisions-3000` | construct | 49.674–78.807× | 0.243× | 0.466× | 0.394× | 0.406× |
| `review-in-collisions-100` | single-use | 1.240–2.016× | 0.628× | 0.724× | 0.702× | 0.701× |
| `review-in-collisions-1000` | single-use | 10.026–16.402× | 0.568× | 0.700× | 0.646× | 0.657× |
| `review-in-collisions-3000` | single-use | 28.139–46.927× | 0.539× | 0.672× | 0.629× | 0.642× |
| `review-subclass-key-eq` | match | wrong answer | 1.305× | 1.236× | 1.225× | 1.214× |
| `review-subclass-key-ne` | match | wrong answer | 1.311× | 1.271× | 1.234× | 1.221× |

`review-*-collisions-*` matching is 0.94–1.01× (before 0.06–0.12×): colliding lists
are no longer hashed, so they scan in order like 1.0.1. Wide-dict empty-operand
construction is 1.00–1.10× (see below). The `per-fix/` run attributes each change:
fix 1 alone removes the wide-container regressions
(`review-wide-list-first-mismatch-1000`/`-10000` rechecked at 0.999–1.010×; see below), fix 2 the wrong answers and fix 3
the collision costs. Fixes 4 and 5 change no measured case beyond noise.

### Remaining cases slower than 1.0.1

Every case initially above 1.03× in the default run was rechecked: 20 case patterns
in `recheck-python-*`, and the five that run missed in `recheck-2-python-*`. One
case beyond its control range but below 1.03×, `review-in-2-1` construction on
3.12 (1.025×), was measured again in the focused check (1.003–1.004×). These remain
slower in the recheck, whose controls were 0.986–1.014×:

| Case | Operation | Recheck 1.0.2 / 1.0.1 | Extra time per call | Cause |
| --- | --- | ---: | ---: | --- |
| `ordered-key-mismatch` | match | 1.124–1.231× | 0.12–0.29 µs | exact-`str` key check (fix 2) |
| `ordered-key-mismatch` | single use | 1.044–1.110× | 0.18–0.68 µs | same |
| `review-subclass-key-{eq,ne}` | match | 1.187–1.309× | 0.18–0.39 µs | failed key check before `equal()` (fix 2) |
| `review-subclass-key-{eq,ne}` | single use (3.10 only) | 1.088× | 0.71–0.75 µs | same |
| `document-scan-*`, `ordered-key-mismatch` | construct (3.10, 3.12, 3.13) | 1.039–1.090× | 0.12–0.40 µs | operand key check at preparation (fix 2) |
| `review-wide-dict-empty-*` | construct (3.10, 3.12, 3.13) | 1.029–1.080× | 0.07–0.32 µs | same, for the empty dict operand |
| `review-in-1-{0,1}` | construct (3.12 only) | 1.038–1.039× | 0.17–0.18 µs | collision guard (fix 3) |
| `date-scan-early` | match (3.10 only) | 1.032× | 0.04 µs | unconverted-type check before date conversion |
| `all-singleton-document-0`, `value-native-document-0`, `document-scan-early` | single use (3.10 only) | 1.023–1.039× | 0.20–0.48 µs | construction cost above |

Per call, that is up to 0.39 µs when matching, 0.40 µs when constructing and
0.75 µs for single use (construction plus one match), largest on 3.10. The
[focused check](#after-the-independent-review) measured the same cases at the head at
up to 0.42 µs when matching and 0.84 µs for single use (`review-subclass-key-ne` on
3.10), and adds a known bounded tradeoff of the same kind,
`review-flat-dict-16-first-mismatch`. At the current head,
`all-singleton-document-0` and `value-native-document-0` single use on 3.10 read
1.005–1.009×; `document-scan-early` still reads 1.031×.

Initially flagged and cleared on recheck:
`review-wide-list-first-mismatch-1000`/`-10000` (0.999–1.010×), `value-array-0`,
`elem-match-value-all-99`, `mod-scan-early`, `mod-float-early`, `all`,
`all-singleton`, `lt-*-array-miss`, `path-eq-0` and `construct-and-100`, and in
`recheck-2-python-*`, `all-singleton-regex-99`, `empty-suffix-indexed-size-None`,
`array-range-element-miss`, `elem-document-last` and `gt-int-float-array-last`
(0.972–1.019×; controls 0.968–1.029×; `empty-suffix-indexed-size-None` read 1.019× on
3.13 and 1.004× in `focused-recheck-python-3.13.json`). The wide-list
cases read 1.185–1.279× in the default run, against controls as low as 0.846×; their
fast-version blocks are short.

### After the independent review

Two later commits change runtime code, and one adds a case:

- [c3a2eb4](https://github.com/weiliddat/mgqpy/commit/c3a2eb4): any `int` or `float` operand at or above
  `sys.hash_info.modulus` in magnitude sends the whole `$in`/`$nin` list to the
  pairwise scan, whatever the other operand types. Before, `[1e100]` scanned but
  `[1e100, None]` was hashed. Results are unchanged.
- [b8b71b5](https://github.com/weiliddat/mgqpy/commit/b8b71b5): flat-container preparation checks the 16-member limit
  before certifying dict keys, so large dict operands never scan their keys.
- `review-flat-dict-16-first-mismatch`: a 16-member dict operand whose document value
  has the same keys in the same order but a wrong first value.

`focused-python-*.json` compares 1.0.1, `before` (a7f0c83) and the head (49783b0) on the 65 cases
these changes can reach: every `$in`/`$nin` case and every case with an equality
operand. It used six processes × 16 blocks × 10 ms per Python, with the four Pythons
running at once on logical CPUs 0, 2, 4 and 6 (separate physical cores). Controls:
matching 0.917–1.070×, construction 0.991–1.014×, single use 0.984–1.011×. Every case
returned its expected boolean.

| Cases | Operation | Head / before | Head / 1.0.1 |
| --- | --- | ---: | ---: |
| `review-wide-dict-first-mismatch-*` | construct, single use | 0.860–0.922× | 0.683–0.751× |
| nested-document operands (`value-document-*`, `value-native-document-*`, `ordered-document`, `all-singleton-document-*`) | construct | 0.945–0.978× | 0.842–0.977× |
| every `$in`/`$nin` case | construct, single use | 0.990–1.011× | 0.159–1.018× |
| list operands | all | 0.990–1.015× | 0.114–1.011× |
| other equality cases | all | 0.986–1.010× | 0.569–1.307× |

Large dict operands no longer scan their keys, and nested-document operands now stop at
their first non-plain value before the key scan. The harness has no mixed `$in` list
with a large number, so c3a2eb4 changes no measured path; int-only lists run the same
code. `in-1000-last` matching read 1.071× head/before on 3.13; a serial recheck read
1.072× with its identical-source control at 0.953× (0.48–0.52 µs per call), and its
matching code is unchanged. Other head/before readings exceed their operation's control
range by at most 0.004 (1.008–1.015×).

**Known bounded tradeoff.** A flat dict of up to 16 plain members is certified and then
compared in C. When the document value's first member already differs, `equal()` would
stop there, so certifying every member costs more:

| `review-flat-dict-16-first-mismatch` | 1.0.2 / 1.0.1 | Extra time per call |
| --- | ---: | ---: |
| match | 1.214–1.381× | 0.29–0.40 µs |
| construct | 1.036–1.075× | 0.26–0.38 µs |
| single use | 1.052–1.104× | 0.49–0.75 µs |

In an uncommitted 3.11 comparison with scratch cases, the same shortcut made a full
hit or late miss of 16 members 0.38–0.68× of 1.0.1, and lowering the cutoff to 8
traded those gains for the cost above. Sizes above 16 use `equal()`. The cutoff and
the design are deliberate.

### Improvements

Matching, 1.0.2 / 1.0.1 per Python, and each version's paired ratio to 0.9.0 in
this run (ranges across the four Pythons):

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | 1.0.1 / 0.9.0 | 1.0.2 / 0.9.0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Numeric-index miss | 0.236× | 0.277× | 0.255× | 0.285× | 7.343–9.167× | 2.092–2.526× |
| `$exists` over subdocuments, last hit | 0.239× | 0.291× | 0.273× | 0.306× | 0.649–0.839× | 0.198–0.200× |
| Subdocument field, last hit | 0.831× | 0.817× | 0.805× | 0.822× | 0.304–0.329× | 0.247–0.268× |
| Flat-document equality, last hit | 0.611× | 0.619× | 0.621× | 0.578× | 0.882–1.049× | 0.542–0.633× |
| Path `$in` of two, last hit | 0.387× | 0.405× | 0.393× | 0.395× | 0.253–0.297× | 0.103–0.117× |
| `$in`, last of 1,000 | 0.004× | 0.005× | 0.005× | 0.004× | 0.199–0.222× | 0.001× |
| Singleton array `$all`, last hit | 0.438× | 0.410× | 0.432× | 0.389× | 11.666–16.236× | 4.802–6.285× |
| Singleton document `$all`, last hit | 1.002× | 1.000× | 1.000× | 0.999× | 14.028–17.951× | 13.960–17.941× |
| Ordered-document equality, last hit | 1.018× | 1.000× | 1.000× | 1.001× | 1.254–1.494× | 1.284–1.494× |

Nested-document equality and singleton document `$all` are unchanged: their members
are compared recursively, as in 1.0.1. Flat-document equality is slower than before
the fixes (0.36–0.39×) because of the length and key checks. Across 310 cases, the
median matching ratio is 0.994–0.997×; identical-source matching controls ranged
0.754–1.164×.

Construction, ranges across the four Pythons (median 0.781–0.832×; controls
0.967–1.023×):

| Construction | 1.0.1 (µs) | 1.0.2 (µs) | 1.0.2 / 1.0.1 |
| --- | ---: | ---: | ---: |
| Flat equality | 2.362–3.368 | 1.486–2.361 | 0.656–0.705× |
| 100-clause `$and` | 223–313 | 148–209 | 0.662–0.703× |
| 10,000-clause `$and` | 26,710–35,839 | 23,876–32,370 | 0.892–0.901× |
| `$in` of 1,000 | 206–335 | 95.079–121 | 0.284–0.528× |
| `$in` of 10,000 | 2,093–3,496 | 928–1,165 | 0.267–0.511× |
| Compiled regex | 10.825–16.433 | 2.728–4.379 | 0.253–0.287× |
| `$regex` string | 5.181–7.701 | 4.103–6.392 | 0.788–0.830× |

Single use, ranges across the four Pythons (median 0.823–0.856×; controls
0.855–1.135×):

| Single use | 1.0.1 (µs) | 1.0.2 (µs) | 1.0.2 / 1.0.1 |
| --- | ---: | ---: | ---: |
| Flat equality | 2.607–4.146 | 1.851–3.131 | 0.712–0.752× |
| Numeric-index miss | 18.064–30.616 | 5.776–8.880 | 0.291–0.335× |
| `$in`, last of 1,000 | 351–562 | 96.529–124 | 0.175–0.316× |
| Singleton array `$all`, last hit | 58.941–88.007 | 29.025–44.993 | 0.438–0.508× |
| Singleton document `$all`, last hit | 108–156 | 108–157 | 0.984–1.007× |

Absolute ranges and ratio ranges are calculated independently.
