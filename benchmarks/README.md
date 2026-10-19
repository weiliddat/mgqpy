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

Results are in [`1.0.2/`](1.0.2/): one JSON/CSV pair per supported Python from a
single three-ref run, plus focused rechecks (`recheck-python-*.json`). The refs are
**0.9.0** ([source](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d)),
**1.0.1** ([source](https://github.com/weiliddat/mgqpy/commit/8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87))
and the **1.0.2 candidate**
([source](https://github.com/weiliddat/mgqpy/commit/73dde3176648a2520414c3b61f45b006b86f60c8),
the rebased #21 runtime; later commits change documentation and results only).
The [0.9.0/1.0.1 baseline](#090-versus-101-baseline) below is unchanged and was
measured on different interpreter patch releases; do not divide across the two.

```sh
for py in 3.10 3.11 3.12 3.13; do
  uv run --no-project --python "$py" python benchmarks/run.py \
    0.9.0=f22a920babc0a37dd07fbe4dae94632f81d9b79d \
    1.0.1=8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87 \
    1.0.2=73dde3176648a2520414c3b61f45b006b86f60c8 \
    --cpu 0 --output "benchmarks/1.0.2/python-$py.json"
done
```

Measured 2026-10-19 with [runner 80321d5](https://github.com/weiliddat/mgqpy/commit/80321d559cf502c79d0d6d7cefe6dff8153792e4)
in a shared Linux x86-64 Amp orb, Intel Xeon @ 2.60 GHz, 8 logical CPUs,
CPython 3.10.20/3.11.6/3.12.13/3.13.13. Interpreters ran serially, pinned to
logical CPU 0, with the defaults (two processes × 12 blocks, all operations).
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

The candidate run exits nonzero: it returns the wrong answer for both
`review-subclass-key-*` controls. 1.0.1 compares keys with `!=`, which this `str`
subclass inherits from `str`, so `{FoldKey("A"): 1}` does not equal `{"a": 1}`.
The candidate's flat-dict path uses Python dict lookup and the subclass's
case-folding `==`, as 0.9.0 did. These two cases have no
1.0.2 ratio. All other 308 cases return their expected boolean in 1.0.1 and 1.0.2.

### Regressions

Every case slower than 1.0.1 beyond that interpreter's identical-source control
range is listed here. They come from two #21 mechanisms, not noise.

**Wide containers rejected early.** Flat-container equality certifies every
member's type before comparing, so it reads the whole document value even when
lengths differ or the first member differs. 1.0.1 rejects these after a length
check or the first member. Matching, 1.0.2 / 1.0.1:

| Case | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | 3.11 µs, 1.0.1 → 1.0.2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `review-wide-dict-empty-100` | 2.890× | 4.282× | 4.199× | 3.816× | 0.578 → 2.466 |
| `review-wide-dict-empty-1000` | 18.826× | 30.699× | 28.973× | 26.952× | 0.599 → 18.346 |
| `review-wide-dict-empty-10000` | 145.858× | 204.471× | 199.340× | 191.500× | 0.929 → 177.914 |
| `review-wide-list-empty-100` | 2.166× | 2.811× | 2.451× | 2.629× | 0.937 → 2.443 |
| `review-wide-list-empty-1000` | 10.223× | 15.413× | 14.030× | 12.070× | 1.064 → 16.238 |
| `review-wide-list-empty-10000` | 82.913× | 135.894× | 114.859× | 108.180× | 1.128 → 153.810 |
| `review-wide-dict-first-mismatch-100` | 1.808× | 2.368× | 2.303× | 2.160× | 1.080 → 2.529 |
| `review-wide-dict-first-mismatch-1000` | 11.464× | 17.158× | 15.239× | 14.417× | 1.088 → 19.254 |
| `review-wide-dict-first-mismatch-10000` | 87.358× | 124.119× | 114.821× | 106.894× | 1.431 → 176.690 |
| `review-wide-list-first-mismatch-100` | 1.555× | 2.238× | 1.955× | 1.867× | 1.112 → 2.531 |
| `review-wide-list-first-mismatch-1000` | 7.105× | 11.344× | 9.618× | 8.589× | 1.520 → 16.585 |
| `review-wide-list-first-mismatch-10000` | 60.922× | 100.004× | 78.697× | 77.954× | 1.551 → 153.926 |

Single use inherits the matching cost where construction does not offset it:
`review-wide-dict-empty-*` is 1.335–1.504× / 4.212–5.994× / 29.842–45.189× at
100 / 1,000 / 10,000 members, and `review-wide-list-empty-*` 1.015–1.165× /
2.353–3.012× / 12.806–20.449×. `review-wide-dict-first-mismatch-1000` and
`-10000` single use are 0.931–1.056× and 0.941–1.066×; the 3.11/3.12 values are
just beyond their single-use controls, and the 1,000-member case rechecked at
1.031–1.066× on 3.11–3.13. Wide-list first-mismatch single use is
faster (0.394–0.722×) because construction skips per-operand preparation.

**Colliding `$in`/`$nin` construction.** An all-plain operand list becomes a
`frozenset`. Integers `i * sys.hash_info.modulus` share one hash, so building the
set costs quadratic equality probes. Construction, 1.0.2 / 1.0.1:

| Case | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | 3.11 µs, 1.0.1 → 1.0.2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `review-in-collisions-100` | 1.939× | 3.083× | 3.022× | 2.911× | 29.0 → 89.2 |
| `review-in-collisions-1000` | 16.851× | 27.205× | 26.837× | 26.063× | 237 → 6,427 |
| `review-in-collisions-3000` | 49.769× | 78.621× | 78.650× | 75.677× | 698 → 54,875 |

`review-nin-collisions-*` are within about 1% of these. Single use is 1.222–2.016× /
10.026–16.402× / 28.139–46.968× at 100 / 1,000 / 3,000 operands. Reused matching
of the same colliding lists is still faster than 1.0.1 (0.060–0.120×).

**Rechecked small differences.** Every other initial ratio above 1.03× was within
its control range. Those cases were rechecked with 1.0.1 and the candidate only,
six processes × 16 blocks × 10 ms (match and single use). The rechecks confirm two
small Python 3.10 costs: `date-scan-early` 1.034× → 1.037× and
`ordered-key-mismatch` 1.047× → 1.033× (controls 0.997× and 1.003×). The
unconverted-type check now runs before date conversion, and swapped-key dicts are
compared by value before key order. Python 3.13 `elem-match-value-all-99` stays at
1.028× (control 0.980×), at the edge of the noise. The other 20 initial
observations (13 cases), 1.030–1.089×, rechecked at 0.951–1.014×: `value-array-0`,
`mod-scan-early`, `mod-float-early`, `gte-int-float-array-last`, `empty-all`,
`empty-all-negated`, `all`, `all-scalar`, `empty-suffix-indexed-size-None`,
`path-eq-0`, `scalar-array-null`, `numeric-miss`, `mixed-miss`. The rechecks also
reproduced `review-wide-list-empty-100` (2.206–3.289× matching) and
`review-wide-dict-first-mismatch-1000` (11.142–17.119×).

### Improvements

Matching, 1.0.2 / 1.0.1 per Python, and each version's paired ratio to 0.9.0 in
this run (ranges across the four Pythons):

| Matching | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | 1.0.1 / 0.9.0 | 1.0.2 / 0.9.0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Numeric-index miss | 0.240× | 0.290× | 0.268× | 0.287× | 7.390–8.946× | 2.050–2.543× |
| `$exists` over subdocuments, last hit | 0.237× | 0.299× | 0.276× | 0.311× | 0.655–0.822× | 0.198–0.208× |
| Subdocument field, last hit | 0.814× | 0.834× | 0.848× | 0.837× | 0.306–0.328× | 0.257–0.277× |
| Flat-document equality, last hit | 0.386× | 0.384× | 0.388× | 0.361× | 0.871–1.023× | 0.335–0.389× |
| Path `$in` of two, last hit | 0.383× | 0.408× | 0.449× | 0.388× | 0.255–0.297× | 0.104–0.131× |
| `$in`, last of 1,000 | 0.004× | 0.005× | 0.005× | 0.004× | 0.206–0.224× | 0.001× |
| Singleton array `$all`, last hit | 0.367× | 0.365× | 0.384× | 0.334× | 11.399–15.428× | 4.181–5.237× |
| Singleton document `$all`, last hit | 1.002× | 0.995× | 0.993× | 1.009× | 14.328–17.714× | 14.286–17.451× |
| Ordered-document equality, last hit | 1.002× | 1.003× | 0.997× | 1.002× | 1.270–1.487× | 1.268–1.495× |

Nested-document equality and singleton document `$all` are unchanged: their
members are compared recursively, as in 1.0.1. Across the 308 comparable cases,
the median matching ratio is 0.995–0.996×; identical-source matching controls
ranged 0.769–1.177×.

Construction, ranges across the four Pythons (median 0.773–0.810×; controls
0.977–1.037×):

| Construction | 1.0.1 (µs) | 1.0.2 (µs) | 1.0.2 / 1.0.1 |
| --- | ---: | ---: | ---: |
| Flat equality | 2.221–3.386 | 1.431–2.293 | 0.657–0.673× |
| 100-clause `$and` | 224–312 | 146–204 | 0.654–0.671× |
| 10,000-clause `$and` | 26,116–35,114 | 23,269–30,065 | 0.853–0.887× |
| `$in` of 1,000 | 203–328 | 74–99 | 0.227–0.420× |
| `$in` of 10,000 | 2,073–3,226 | 696–949 | 0.215–0.404× |
| Compiled regex | 10.773–16.409 | 2.757–4.331 | 0.255–0.293× |
| `$regex` string | 5.179–7.641 | 4.031–6.195 | 0.777–0.812× |

Single use, ranges across the four Pythons (median 0.825–0.844×; controls
0.877–1.070×):

| Single use | 1.0.1 (µs) | 1.0.2 (µs) | 1.0.2 / 1.0.1 |
| --- | ---: | ---: | ---: |
| Flat equality | 2.706–4.172 | 1.854–3.024 | 0.689–0.732× |
| Numeric-index miss | 18.197–30.663 | 5.948–8.757 | 0.284–0.332× |
| `$in`, last of 1,000 | 345–554 | 75–100 | 0.135–0.252× |
| Singleton array `$all`, last hit | 58.752–89.293 | 25.753–39.091 | 0.392–0.446× |
| Singleton document `$all`, last hit | 109.524–157.181 | 108.658–156.015 | 0.984–1.002× |

Absolute ranges and ratio ranges are calculated independently. Eligible 0.9.0
comparisons: 252 cases on Python 3.10 and 258 on 3.11–3.13; 0.9.0 wrong answers,
rejections and crashes remain flagged in each CSV/JSON and have no ratio.

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
