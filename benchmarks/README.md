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
have both measurements. Dataset definitions live in `test_benchmarks.py`.

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
