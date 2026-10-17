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
timings. Dataset definitions live in `test_benchmarks.py`.

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
Arrays still evaluate every element before `any()`, preserving evaluation order
and the whole-document non-match policy on evaluation errors.

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
Traversal semantics and eager array evaluation are unchanged; no path cache or
new traversal representation is introduced.

The expanded pytest-benchmark suite passes all 26 matching/construction cases.
A separate short run on Python 3.11 measured construction at 207 µs for large
`$in`, 4.917 µs for `$mod`, 2.585 µs for `$size`, and 3.477 µs for regex, using
`--benchmark-min-rounds=5 --benchmark-max-time=0.1 --benchmark-disable-gc`.
The snapshot copier is unchanged.
