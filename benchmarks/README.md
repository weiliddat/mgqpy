# Matching and construction baseline

These CPU-only benchmarks are opt-in, independent of MongoDB and the correctness
suite. `uv run pytest` collects only `tests/`; run these explicitly:

```sh
uv run pytest benchmarks --benchmark-min-rounds=30 --benchmark-max-time=0.5 \
  --benchmark-warmup=on --benchmark-disable-gc --benchmark-json=/tmp/mgqpy-bench.json
```

`test_match` constructs the predicate outside the timed region and evaluates one
matching document per invocation. `test_construct` times only `Query(query)`;
its assertion evaluates the result outside the timed region. Regex construction
uses Python's warm regex cache. Flat equality, a five-segment dict path, 100
subdocuments, a 1,000-member `$in`, explicit regex, and combined `$and`/`$or` each
have both measurements. Additional cases cover single-/two-digit indexed paths,
scalar/deep `$size`, and scalar/deep/100-value-array `$mod`, also with construction
timings. Array `$mod` has both an early match and a last-element match to measure
short-circuiting separately from full-scan cost. Dataset definitions live in
`test_benchmarks.py`.

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

No measured matching regression against 0.9.0 on any interpreter. The Python
3.10 regex baseline still fails with `re.NOFLAG`; the final source matches at
1.537 µs. These are shared-orb medians, not universal guarantees or CI thresholds.
The final opt-in suite passes all 28 cases. A short Python 3.11 run with the same
pytest-benchmark flags as above measured construction at 206.312 µs for large
`$in`, 4.481 µs for `$mod`, 2.523 µs for `$size`, and 3.318 µs for regex.
Construction and the snapshot copier are unchanged by the evaluation-policy fix.
