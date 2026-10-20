# Versioned performance benchmarks

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
fresh processes/16 blocks and inspect identical-source variation. Report the initial
run too; disclose which cases were rechecked instead of selecting favorable runs.
These are warmed CPU-only shared-machine observations, not CI thresholds,
latency guarantees, memory measurements or application-distribution benchmarks.

## Current snapshot

[`snapshot/`](snapshot/) holds one CSV/JSON pair per supported Python. Each run
measures **0.9.0** ([source](https://github.com/weiliddat/mgqpy/commit/f22a920babc0a37dd07fbe4dae94632f81d9b79d)),
**1.0.1** ([source](https://github.com/weiliddat/mgqpy/commit/8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87))
and **1.0.2** ([source](https://github.com/weiliddat/mgqpy/commit/4615072fb940c19cda4313f08e9a12126eee0976))
together. The JSON omits the raw per-block samples to save space. It keeps the
hardware, configuration, hashes, statuses and per-case medians, and each timing adds
`paired_ratio_to_previous`: the 1.0.2 / 1.0.1 median of the paired block ratios.

```sh
for py in 3.10 3.11 3.12 3.13; do
  uv run --no-project --python "$py" python benchmarks/run.py \
    0.9.0=f22a920babc0a37dd07fbe4dae94632f81d9b79d \
    1.0.1=8addeeec3c6aed6d534b1b2b46ecd61e3d29fd87 \
    1.0.2=4615072fb940c19cda4313f08e9a12126eee0976 \
    --output "/tmp/snapshot/python-$py.json"
done
```

Then copy the CSVs to `benchmarks/snapshot/` and write each JSON there without its
samples, running this as `python slim.py SOURCE.json DESTINATION.json`:

```python
import json, statistics, sys
d = json.load(open(sys.argv[1]))
prev, last = list(d["refs"])[-2:]
for i, row in enumerate(d["results"]):
    for op, timing in row["timings"].items():
        if row["status"][prev]["eligible"] and row["status"][last]["eligible"]:
            ratios = [b / a for run in d["runs"]
                      for s in [run["rows"][i]["timings"][op]["samples_us"]]
                      for a, b in zip(s[prev], s[last])]
            timing["paired_ratio_to_previous"] = statistics.median(ratios)
d["runs"] = [{k: v for k, v in run.items() if k != "rows"} for run in d["runs"]]
d["samples"] = "omitted; per-case medians and paired ratios are in results"
json.dump(d, open(sys.argv[2], "w"), separators=(",", ":"))
```

Measured 2026-10-20 with the runner from the 1.0.2 source, in a shared Linux x86-64
Amp orb (Intel Xeon @ 2.60 GHz, 8 logical CPUs). Interpreters ran serially, pinned to
logical CPU 0 with `--cpu 0` (Linux only), with the defaults: two processes × 12 blocks, all operations. Every case
returned its expected boolean in 1.0.1 and 1.0.2, and all four runs exit 0.

| CPython | Eligible against 0.9.0, of 311 | Identical-source matching | Construction | Single use |
| --- | ---: | ---: | ---: | ---: |
| 3.10.20 | 253 | 0.807–1.120× | 0.986–1.045× | 0.848–1.152× |
| 3.11.6 | 259 | 0.764–1.077× | 0.976–1.029× | 0.902–1.102× |
| 3.12.13 | 259 | 0.896–1.159× | 0.980–1.016× | 0.903–1.094× |
| 3.13.13 | 259 | 0.702–1.190× | 0.977–1.021× | 0.864–1.232× |

The 58 cases flagged on 3.10 and 52 on 3.11+ are 0.9.0 rejections, exceptions and
wrong answers; 3.10 adds 0.9.0's explicit-regex failures. Ratios below are medians of
paired block ratios, lower is faster. Across the 311 cases, the median 1.0.2 / 1.0.1
ratio is 0.986–0.996× for matching, 0.780–0.822× for construction and 0.818–0.856× for
single use, depending on the Python.

| Matching, 1.0.2 / 1.0.1 | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | 1.0.1 / 0.9.0 | 1.0.2 / 0.9.0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Numeric-index miss | 0.238× | 0.306× | 0.272× | 0.291× | 7.308–8.950× | 2.008–2.581× |
| `$exists` over subdocuments, last hit | 0.246× | 0.299× | 0.284× | 0.309× | 0.653–0.831× | 0.199–0.206× |
| Subdocument field, last hit | 0.839× | 0.835× | 0.832× | 0.823× | 0.309–0.331× | 0.259–0.272× |
| Flat-document equality, last hit | 0.605× | 0.608× | 0.622× | 0.580× | 0.888–1.031× | 0.546–0.630× |
| Path `$in` of two, last hit | 0.389× | 0.406× | 0.408× | 0.397× | 0.257–0.291× | 0.106–0.118× |
| `$in`, last of 1,000 | 0.004× | 0.005× | 0.005× | 0.005× | 0.207–0.221× | 0.001× |
| Singleton array `$all`, last hit | 0.432× | 0.420× | 0.434× | 0.383× | 11.424–16.364× | 4.778–6.300× |
| Singleton document `$all`, last hit | 0.998× | 0.995× | 0.998× | 0.997× | 14.401–17.570× | 14.167–17.288× |
| Ordered-document equality, last hit | 0.990× | 0.971× | 1.001× | 0.996× | 1.275–1.488× | 1.250–1.487× |

Nested-document equality and singleton document `$all` compare their members
recursively, as in 1.0.1, so they are unchanged and remain much slower than 0.9.0.

Construction and single use, ranges across the four Pythons. 0.9.0's constructor
stores a reference; 1.x copies, validates and compiles the query, so construction has
no 0.9.0 ratio.

| Construction | 0.9.0 (µs) | 1.0.1 (µs) | 1.0.2 (µs) | 1.0.2 / 1.0.1 |
| --- | ---: | ---: | ---: | ---: |
| Flat equality | 0.108–0.194 | 2.146–3.401 | 1.432–2.349 | 0.665–0.692× |
| 100-clause `$and` | 0.192–0.272 | 220–312 | 146–208 | 0.664–0.690× |
| 10,000-clause `$and` | 0.329–0.385 | 25,868–36,779 | 23,339–32,528 | 0.886–0.903× |
| `$in` of 1,000 | 0.192–0.267 | 202–329 | 94.682–121 | 0.287–0.518× |
| `$in` of 10,000 | 0.258–0.346 | 2,028–3,199 | 883–1,171 | 0.276–0.515× |
| Compiled regex | 0.104–0.200 | 10.584–16.540 | 2.641–4.354 | 0.249–0.283× |
| `$regex` string | 0.103–0.203 | 5.022–7.774 | 3.961–6.329 | 0.788–0.828× |

| Single use | 0.9.0 (µs) | 1.0.1 (µs) | 1.0.2 (µs) | 1.0.2 / 1.0.1 | 1.0.2 / 0.9.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Flat equality | 1.298–2.337 | 2.553–4.183 | 1.848–3.089 | 0.722–0.742× | 1.322–1.473× |
| Numeric-index miss | 1.832–3.359 | 17.886–30.674 | 5.697–8.799 | 0.286–0.340× | 2.596–3.291× |
| `$in`, last of 1,000 | 630–1,068 | 344–558 | 96.361–122 | 0.172–0.313× | 0.090–0.163× |
| Singleton array `$all`, last hit | 3.764–5.836 | 58.791–89.723 | 28.852–44.696 | 0.439–0.495× | 5.928–7.622× |
| Singleton document `$all`, last hit | 6.458–9.001 | 109–157 | 108–158 | 0.989–0.999× | 14.786–18.449× |

Absolute ranges and ratio ranges are calculated independently.

Colliding `$in`/`$nin` lists (`review-{in,nin}-collisions-*`) are not hashed, so they
match like 1.0.1 (0.973–1.010×) and construct at 0.248–0.578×. Empty dict and list
operands against wide values match at 0.721–0.953×; same-length wide values whose
first member differs match at 0.977–1.006× after the recheck below.

### Remaining cases slower than 1.0.1

Every observation above 1.03× 1.0.2 / 1.0.1 in the snapshot (34 case/operation pairs
over 27 cases) was rechecked on all four Pythons with 1.0.1 and 1.0.2 only: six processes × 16
blocks × 10 ms, the four Pythons at once on logical CPUs 0, 2, 4 and 6. The rechecks were
run but are not stored. Their identical-source controls were 0.988–1.031× for matching,
0.993–1.010× for construction and 0.993–1.020× for single use.

| Case | Operation | Snapshot | Recheck | Extra per call | Cause |
| --- | --- | ---: | ---: | ---: | --- |
| `review-flat-dict-16-first-mismatch` | match | 1.192–1.378× | 1.211–1.382× | 0.29–0.39 µs | certifies all 16 members (see below) |
| `review-flat-dict-16-first-mismatch` | construct | 1.033–1.079× | 1.026–1.076× | 0.21–0.37 µs | same |
| `review-flat-dict-16-first-mismatch` | single use | 1.041–1.109× | 1.042–1.111× | 0.36–0.71 µs | same |
| `review-subclass-key-{eq,ne}` | match | 1.202–1.275× | 1.205–1.300× | 0.18–0.42 µs | key check fails before `equal()` |
| `review-subclass-key-{eq,ne}` | single use (3.10) | 1.078–1.097× | 1.082–1.094× | 0.63–0.81 µs | same |
| `ordered-key-mismatch` | match | 1.112–1.223× | 1.117–1.217× | 0.11–0.29 µs | flat-dict shortcut fails on key order, then `equal()` |
| `ordered-key-mismatch` | single use | 1.061–1.107× | 1.050–1.097× | 0.23–0.59 µs | same, plus construction |
| `ordered-key-mismatch`, `document-scan-*` | construct (not 3.11) | 1.038–1.102× | 1.033–1.090× | 0.10–0.38 µs | operand key check |
| `review-wide-dict-empty-*` | construct (not 3.11) | 1.020–1.090× | 1.017–1.074× | 0.04–0.25 µs | same, for the empty operand |
| `review-in-1-{0,1}` | construct (3.12) | 1.033–1.036× | 1.031–1.034× | 0.14–0.16 µs | collision guard |

Per call, that is up to 0.42 µs when matching, 0.38 µs when constructing and 0.81 µs
for single use, largest on 3.10. On 3.11 those construction cases read 0.983–1.013×,
and `review-in-1-1` construction on 3.10 reads 1.016× (0.08 µs). The other 17
observations read 0.935–1.018× on recheck, within their controls:
`review-wide-list-first-mismatch-{1000,10000}` (1.075–1.173× in the snapshot against
controls as low as 0.854×; their fast-version blocks are short), `value-array-0`,
`mod-{scan,float,decimal}-early`, `date-scan-early`, `uuid-scan-early`, `path-eq-0`,
`{gt,lt}-int-float-array-miss`, `numeric-miss`, `empty-all`, `and-or`,
`all-elem-match-document`, and `document-scan-early` and `review-wide-dict-empty-100`
single use.

**Known bounded tradeoff.** A flat dict of up to 16 plain members is certified and then
compared in C. When the document value's first member already differs, `equal()` would
stop there, so certifying every member costs more; that is
`review-flat-dict-16-first-mismatch` above. In return a full hit or late miss of 16
members takes 0.38–0.68× of 1.0.1's time (an uncommitted 3.11 comparison with scratch
cases), and lowering the cutoff to 8 traded those gains for the cost above. Sizes above 16
use `equal()`. The cutoff and the design are deliberate.

Earlier rounds on #21 (the pre-fix snapshot, per-fix attribution and focused checks)
are summarised in [HISTORY.md](HISTORY.md#102-review-rounds-on-21).

## Case inventory and the claims it supports

There are **311 cases**, with all three operations available for every eligible
case: 202 original matching fixtures + 56 whole-stack additions + 53 controls.
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
| Membership crossover and compatibility controls | `review-in-{1,2,10}-*`, `review-flat-list`, `review-subclass-key-{eq,ne}`, `review-flat-dict-16-first-mismatch` |

The exact recovered cases back all published workload rows. They do **not** make
all historical claims reproducible from refs: eager/generator comparison columns
used temporary AST rewrites, and the guard-only numeric experiment used a monkey
patch. Neither is retained as another execution mode. Historical branch gates
used different source revisions and stronger selective rechecks; this snapshot
does not claim to repeat those gates. 0.9 explicit regex on Python 3.10 cannot be
timed because `re.NOFLAG` is missing. Wrong/rejected old results remain in the
output. The current snapshot measures #21's changes, including its review fixes,
with these cases.

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

## Updating the snapshot and retired tooling

The repository keeps **one current snapshot**: 0.9.0, the previous release and the
current release measured together in one run per supported Python. It is replaced
only when runtime code changes, by a full rerun on one machine. Before a release
that changes matching, traversal, comparison, validation, construction or supported
Pythons, compare the previous release with the candidate on all supported Pythons
as a quick check against the snapshot's ballpark; those runs and their rechecks are
not committed. Add representative cases for newly affected shapes before measuring,
and keep existing cases stable. When the snapshot is replaced, update the
[current snapshot](#current-snapshot) section with source IDs, environment, per-case
changes, noise and a summary of the rechecks, and move the superseded tables to
[HISTORY.md](HISTORY.md). Prefer comparing refs in a fresh run over dividing
absolute times from different machines. There is no performance workflow or CI gate.

Removed/replaced:

- `test_benchmarks.py`: all 202 matching and 27 construction fixtures are preserved
  in `cases.py`; sequential pytest timings are replaced by paired ref comparisons.
- The `pytest-benchmark` dev dependency and its `py-cpuinfo` dependency: the runner
  uses standard-library `timeit`/`time.process_time` and needs neither.
- Old pytest timing and manual `PYTHONPATH` instructions: replaced by `run.py`;
  previous numbers and measurement context are preserved in `HISTORY.md`.

`uv run pytest` still collects only `tests/`. To check the runner's CLI behavior
without a performance gate, run `uv run pytest benchmarks/test_harness.py -q`.
