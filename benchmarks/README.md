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
of the runner and cases. The temporary source trees are removed afterward.
Avoid other CPU-heavy work while running; run interpreters serially. On Linux
the workers pin to the first available logical CPU, or the supplied `--cpu`.
Elsewhere affinity is unavailable and recorded as `null`.

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
