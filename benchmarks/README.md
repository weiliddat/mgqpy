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

## 0.9.0 versus the v1 base

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
filtering many documents. In particular, copying/validating 1,000 `$in` operands
now costs about 0.43 ms. Regex matching avoids repeated flag parsing/compilation.
In this run, non-regex matching was about 8–12% slower, combined logical matching
was essentially unchanged, and regex matching was about 39% faster. Remeasure on
the same machine before drawing optimization conclusions from these small cases.

To repeat the old-source comparison without changing the checkout, extract the
linked baseline commit's `src/` with `git archive` into a temporary directory.
Run the current benchmark file using the same interpreter with
`PYTHONPATH=/path/to/baseline/src .venv/bin/python -m pytest benchmarks ...`, then
run again without that `PYTHONPATH`. Check `mgqpy.__file__` before measuring so
the baseline run cannot accidentally import the editable installation.
