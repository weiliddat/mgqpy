# Versioned performance baseline

`run.py` compares **any two or more local git refs/tags**, without checking them
out or installing mgqpy. It needs Git and Python 3.10+, not MongoDB, pytest or
pytest-benchmark. It extracts only `src/` with `git archive`; uncommitted runtime
edits are **not** measured. The case definitions always come from this checkout's
[`cases.py`](cases.py), independently of the versions being compared.

## Run before a release that may affect performance

Run from the repository root. Fetch the refs first; in a shallow clone, fetch
the missing history (`git fetch --unshallow origin`). Labels are optional; the
first ref is the baseline, and all later refs are compared with it.

```sh
python benchmarks/run.py --list
python benchmarks/run.py previous=origin/main candidate=HEAD --output /tmp/mgqpy.json

# Check all answers without timing, or rerun a small set with stronger sampling.
python benchmarks/run.py origin/main HEAD --check --output /tmp/check.json
python benchmarks/run.py origin/main HEAD --cases 'review-wide-*' '*collisions*' \
  --processes 6 --blocks 16 --seconds .01 --output /tmp/recheck.json

# More than two refs; matching alone if construction is irrelevant to this check.
python benchmarks/run.py old=origin/main previous=HEAD~1 candidate=HEAD \
  --operations match --output /tmp/three-way.json
```

Each timed run writes **JSON with raw paired samples and CSV with per-case
medians/ratios**, beside one another. Ref names resolve to full commit IDs before
extraction. JSON records Python, platform, affinity, settings and SHA-256 hashes
of the runner and cases, plus best-effort CPU model, logical CPU count, physical
memory in bytes and OS (`null` when unavailable). Temporary source trees are
removed afterward.
Avoid other CPU-heavy work while running; run interpreters serially. On Linux
the workers pin to the first available logical CPU, or the supplied `--cpu`.
Elsewhere affinity is unavailable and recorded as `null`.

Comparisons are valid only between versions measured together in the same run on
the same hardware. When hardware changes, rerun all versions together on that
machine rather than comparing against saved numbers from another machine.

The default operations are measured independently:

- **`match`:** `predicate.test(document)`, with the predicate constructed outside
  timing and reused.
- **`construct`:** `Query(query)` only, including destruction; verification is
  outside timing. Regex and path caches are warm, not cold-start measurements.
- **`single-use`:** actual `Query(query).test(document)`, including destruction.
  This is not the sum of separately measured construction and matching medians.

Every case has a literal expected boolean. The runner records construction,
legacy `validate()`, and evaluation errors by phase, type and message. It flags
wrong answers, unsupported queries and differing outcomes. Matching/single-use
ratios require both versions to validate and produce the expected boolean;
wrong answers and crashes are **never speedups**. Construction may still have an
absolute timing for a legacy unchecked constructor, but no ratio for an ineligible
case. Even eligible 0.9 construction is a different contract: it stores a
reference, whereas 1.x copies, validates and compiles the whole query.

Unexpected **last-ref** outcomes exit nonzero after saving evidence. Known older
differences remain flagged but do not fail the run. Use `--allow-differences` only
after reviewing an intentional last-ref semantic change; it does not manufacture
comparability. This is a workload check, not a replacement for the MongoDB
correctness suite or a comprehensive semantic differential.

## Paired measurements and noise

The method follows the whole-stack audit and polish gate in [HISTORY.md](HISTORY.md):

1. Two fresh worker processes import each source independently, reversing import
   order on the second. Package paths, retained circular package references and
   distinct `Query` classes are checked. The last source is independently imported
   once more as an **identical-source control for every case/operation**.
   Each variant's `mgqpy` module cache is activated outside its timed blocks,
   retaining deferred imports. Variants get separate deep copies of the fixtures;
   untimed serialized checks reject mutations, including dictionary key order.
2. Verify outcomes, warm each function 100 times, then calibrate on 100 calls of
   the slowest participating variant to target **5 ms process CPU time** per
   block. All variants use the same count, bounded to 20–100,000 calls.
3. Run 12 paired blocks per process. Shuffle timing order with
   `random.Random(4361 + case_index + 1000 * operation_index)`; filtering cases or
   operations does not renumber seeds. `timeit` disables GC during timing;
   collect between blocks. Workers use `PYTHONHASHSEED=0`.
4. Pool all 24 paired block ratios and report their median, **not the ratio of
   medians**, best process or a workload average. Absolute µs are pooled medians.
   The control compares the duplicate last source with the original last source;
   it is not a correction factor applied to results.

The 5 ms target is for the slowest variant, not every variant. When versions differ
by orders of magnitude, a fast version can have much shorter blocks and noisier
absolute/control timings even with the minimum count. Compare nearby release
refs when investigating small costs; the 0.9/1.0.1 run establishes broad changes,
not a precision bound on every sub-microsecond workload.

A case whose ratio is within or near that interpreter's same-source control range
for the operation is inconclusive and needs a focused nearby-ref recheck. This is
a recheck convention, not a pass/fail threshold or a confidence interval.

Report individual regressions, including full scans and early rejections. Do not
hide them in an average speedup. Recheck suspected small regressions with six
fresh processes/16 blocks and inspect identical-source variation. Keep the initial
run too; disclose which cases were rechecked instead of selecting favorable runs.
These are warmed CPU-only shared-machine observations, not CI thresholds,
latency guarantees, memory measurements or application-distribution benchmarks.

## 1.0.2 versus 1.0.1

Results are in [`1.0.2/`](1.0.2/), one JSON/CSV pair per supported Python for each run:

- `python-*.json`: **0.9.0** ([source](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d)),
  **1.0.1** ([source](https://github.com/weiliddat/mgqpy/commit/8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87)) and the
  **1.0.2 candidate** ([source](https://github.com/weiliddat/mgqpy/commit/a7f0c83140129c7e9c9bf1c8da4ca61747d986a8)) in one
  default run per interpreter. Later commits change documentation and results only.
- `recheck-python-*.json`: focused rechecks of every case initially above 1.03×.
- `per-fix/`: 1.0.1, the pre-fix candidate and each review-fix commit on the target
  cases, to attribute changes to individual commits.
- `before-fixes/`: the first snapshot, of [73dde31](https://github.com/weiliddat/mgqpy/commit/73dde3176648a2520414c3b61f45b006b86f60c8),
  before the review fixes. It is kept for comparison; the tables below use the
  post-fix run unless a column says otherwise.

The [0.9.0/1.0.1 baseline](#090-versus-101-baseline) below is unchanged and was
measured on different interpreter patch releases; do not divide across the two.

```sh
for py in 3.10 3.11 3.12 3.13; do
  uv run --no-project --python "$py" python benchmarks/run.py \
    0.9.0=f22a920babc0a37dd07fbe4dae94632f81d9b79d \
    1.0.1=8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87 \
    1.0.2=a7f0c83140129c7e9c9bf1c8da4ca61747d986a8 \
    --cpu 0 --output "benchmarks/1.0.2/python-$py.json"
done
```

Measured 2026-10-19/20 with [runner 80321d5](https://github.com/weiliddat/mgqpy/commit/80321d559cf502c79d0d6d7cefe6dff8153792e4)
in a shared Linux x86-64 Amp orb, Intel Xeon @ 2.60 GHz, 8 logical CPUs,
CPython 3.10.20/3.11.6/3.12.13/3.13.13: the same machine and interpreters as the
pre-fix snapshot. Interpreters ran serially, pinned to logical CPU 0, with the
defaults (two processes × 12 blocks, all operations). Rechecks used six processes ×
16 blocks × 10 ms. Every case returned its expected boolean in 1.0.1 and 1.0.2; all
four runs exit 0. Eligible 0.9.0 comparisons: 252 cases on Python 3.10 and 258 on
3.11–3.13.

The CSV ratio column compares each ref with the first (0.9.0). The **1.0.2 / 1.0.1**
ratios below pair the same blocks from the JSON's raw samples, using the README's
median of all 24 per-block ratios:

```python
import json, statistics
data = json.load(open("benchmarks/1.0.2/python-3.11.json"))
for i, row in enumerate(data["results"]):
    for op in row["timings"]:
        old = [v for run in data["runs"] for v in run["rows"][i]["timings"][op]["samples_us"].get("1", [])]
        new = [v for run in data["runs"] for v in run["rows"][i]["timings"][op]["samples_us"].get("2", [])]
        if old and row["status"]["1"]["eligible"] and row["status"]["2"]["eligible"]:
            print(row["name"], op, statistics.median(b / a for a, b in zip(old, new)))
```

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

Every case beyond its interpreter's identical-source control range in the default
run, or initially above 1.03×, was rechecked. These remain slower in the recheck,
whose controls were 0.986–1.014×:

| Case | Operation | Recheck 1.0.2 / 1.0.1 | Cause |
| --- | --- | ---: | --- |
| `ordered-key-mismatch` | match | 1.124–1.231× | exact-`str` key check (fix 2) |
| `ordered-key-mismatch` | single use | 1.044–1.110× | same |
| `review-subclass-key-{eq,ne}` | match | 1.187–1.309× | failed key check before `equal()` (fix 2) |
| `review-subclass-key-{eq,ne}` | single use (3.10 only) | 1.088× | same |
| `document-scan-*`, `ordered-key-mismatch` | construct (3.10, 3.12, 3.13) | 1.039–1.090× | operand key check at preparation (fix 2) |
| `review-wide-dict-empty-*` | construct (3.10, 3.12, 3.13) | 1.029–1.080× | same, for the empty dict operand |
| `review-in-1-{0,1}` | construct (3.12 only) | 1.038–1.039× | collision guard (fix 3) |
| `date-scan-early` | match (3.10 only) | 1.032× | unconverted-type check before date conversion |
| `all-singleton-document-0`, `value-native-document-0`, `document-scan-early` | single use (3.10 only) | 1.023–1.039× | construction cost above |

These are absolute costs of 0.1–0.4 µs. Initially flagged and cleared on recheck:
`review-wide-list-first-mismatch-1000`/`-10000` (0.999–1.010×), `value-array-0`,
`elem-match-value-all-99`, `mod-scan-early`, `mod-float-early`, `all`,
`all-singleton`, `lt-*-array-miss`, `path-eq-0` and `construct-and-100`. The wide-list
cases read 1.185–1.279× in the default run, against controls as low as 0.846×; their
fast-version blocks are short.

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

## 0.9.0 versus 1.0.1 baseline

The full baseline is in [`baseline/`](baseline/): one JSON/CSV pair per supported
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

## Case inventory and the claims it supports

There are **310 cases**, with all three operations available for every eligible
case: 202 original matching fixtures + 56 whole-stack additions + 52 controls.
The original 27 construction fixtures are a subset of the 202; none were lost.
Names and expected results are listed by `--list`; the executable query/document
definitions live in one file rather than a second inventory of copied inputs.
Early/last/miss scans have 100 candidates, deciding at 0/99/absent unless named
otherwise. `None` in older case names means all miss, not a null operand.

| Past claim / concern | Cases |
| --- | --- |
| Initial 0.9/base, revised-base and compiled-path gains | `flat`, `deep`, `subdocuments`, `large-in`, `regex`, `and-or`, plus `*-miss`/`*-missing`, `subdocs-*` and `in-1000-*` |
| Numeric/indexed follow-up; short-circuit versus full scan | `indexed-eq*`, `size`, `deep-size`, `mod`, `deep-mod`, `array-mod`, `array-mod-last`, `mod-scan-*` |
| Mixed numeric regression/fix | 32 `{gt,gte,lt,lte}-{int-float,float-int}-*`, eight same-type scalar controls, `deep-mixed-range`, `numeric-*`, `mixed-*` |
| Shared traversal, literal numeric alternatives and newly required work | `path-{eq,in,exists,size,all,elem-match}-*`, `numeric-field`, `indexed-miss`, `index-alternative-*`, `scalar-array-null`, `nested-leaf`, `missing-null`, `empty-all*` |
| Shared recursive comparison/native conversion costs | `ordered-document`, `value-*`, `document-scan-*` (flat dict), `range-{document,binary}-*`, `document-range-scan-*`, `array-range-scan-*`, `date-scan-*`, `uuid-scan-*`, NaN/bool/type/container controls |
| Bounded numeric/string `$all` prefixes; full-scan controls | `all-{number,string}-{0,98,None}`, `all-*-prefix-{10000,100000}`, `all-*-shifted-prefix` |
| Singleton lowering, value-form elemMatch, empty suffixes and ordinary-path gate | `all-singleton-*`, `elem-match-value-*`, `all-elem-match-*`, `empty-suffix*`, `indexed-list-*` (including depth 4/8/16) |
| v1-polish gate and new sNaN behavior | All 258 original/audit cases include its 254 comparable controls and two sNaN cases; `mod-{float,decimal}-*`, `mod-reject-*`, `mod-snan-*` retain numeric guards |
| 1.0.1 Unicode restoration | `regex-unicode-ignorecase`, `regex-unicode-class` and explicit/implicit/singleton regex scans |
| CHANGELOG matching/single-use table | `flat`, `mixed-last`, `in-1000-last`, `all-number-98`, `value-document-{99,None}`, `indexed-miss`, `all-singleton-{document,array}-{99,None}`; wide logical cost: `and-*`, `or-*` |
| #21 table, matching | `indexed-miss`, `path-exists-99`, `subdocs-last`, `document-scan-last`, `all-singleton-{array,document}-99`, `path-in-99`, `in-1000-last` |
| #21 table, construction | `flat`, `and-early`, `in-1000-last`, `implicit-regex-early` (compiled pattern), `regex` (string); additional Unicode compiled pattern: `review-compiled-regex` |
| #21 uncovered early-rejection costs | `review-wide-{dict,list}-empty-*`, `review-wide-{dict,list}-first-mismatch-*` at 100/1,000/10,000 members; explicit index selects whole inner lists |
| #21 hash-collision construction | `review-{in,nin}-collisions-{100,1000,3000}`; integers `i * sys.hash_info.modulus`, intentionally outside BSON int64 |
| Wide whole documents / large construction | `wide-document-{hit,miss}-*`, `construct-{in,and}-*` at 100/1,000/10,000; `review-wide-and` fails at its first field but compiles 100 clauses |
| Membership crossover and compatibility controls | `review-in-{1,2,10}-*`, `review-flat-list`, `review-subclass-key-{eq,ne}` |

The exact recovered cases back all published workload rows. They do **not** make
all historical claims reproducible from refs: eager/generator comparison columns
used temporary AST rewrites, and the guard-only numeric experiment used a monkey
patch. Neither is retained as another execution mode. Historical branch gates
used different source revisions and stronger selective rechecks; this baseline
does not claim to repeat those gates. 0.9 explicit regex on Python 3.10 cannot be
timed because `re.NOFLAG` is missing. Wrong/rejected old results remain in the
output. No #21 performance claim is independently remeasured by this baseline;
the broader controls are here to measure its fixes later.

Undefined compiled-regex flags from the review are not a timed workload: their
acceptance already differs between Python 3.10 and 3.11 in 1.0.1, and unsupported
flags are outside the documented regex contract. The eight same-type numeric
controls and deep numeric control are reconstructed from the earlier gate's
description, including inclusive-boundary inputs; the 258 original/audit fixtures
were checked exactly against the recovered author harness.

Provenance: [base/numeric work](https://ampcode.com/threads/T-01a148f8-570e-728c-aaa5-583247439e00),
[paths/values/operators/polish/1.0.1](https://ampcode.com/threads/T-01a14967-c712-750e-a24b-2c1fc517bf5f),
[whole-stack and single-use audit](https://ampcode.com/threads/T-01a1501d-1e84-72cb-a699-fb211f3e851d),
[#21 author](https://ampcode.com/threads/T-bf67fd37-6fbc-416e-8910-4e21d71572d7),
[#21 review](https://ampcode.com/threads/T-01a154f6-2fdd-7299-8a2e-5066a877cfa2),
[critique](https://ampcode.com/threads/T-01a154f6-ceeb-77dc-96c2-1cf257ea22e0),
[thermos](https://ampcode.com/threads/T-01a154f6-d75e-751e-9fd4-e9d5842a21a6).
The review's `check.py`, `bench.py`, `summarize.py` were recovered directly;
their targeted cases and timing method are integrated here, not their large
fuzzing corpus or hard-coded three-version runner. [Historical tables](HISTORY.md)
retain the prior numbers and their original caveats.

## Updating the baseline and retired tooling

Before releases that change matching, traversal, comparison, validation,
construction or supported Pythons, compare the previous release with the candidate
on all supported Pythons. Add representative cases for newly affected shapes
before measuring. Keep existing cases stable; explain deliberate input/expectation
changes. Save new result pairs in a release-named directory, keep the original
baseline, and update this README with source IDs, environment, per-case changes,
noise and exclusions. Prefer comparing refs in a fresh run over dividing absolute
times from different machines. There is no performance workflow or CI gate.

Removed/replaced:

- `test_benchmarks.py`: all 202 matching and 27 construction fixtures are preserved
  in `cases.py`; sequential pytest timings are replaced by paired ref comparisons.
- The `pytest-benchmark` dev dependency and its `py-cpuinfo` dependency: the runner
  uses standard-library `timeit`/`time.process_time` and needs neither.
- Old pytest timing and manual `PYTHONPATH` instructions: replaced by `run.py`;
  previous numbers and measurement context are preserved in `HISTORY.md`.

`uv run pytest` still collects only `tests/`. To check the runner's CLI behavior
without a performance gate, run `uv run pytest benchmarks/test_harness.py -q`.
