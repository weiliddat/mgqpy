#!/usr/bin/env python3
"""Render RESULTS.md from the slim JSON files in a results directory.

    python benchmarks/compare/report.py benchmarks/compare/results

Inputs: compat.json, perf.json (headline Python), perf-<version>.json (optional
Python checks) and perf-js.json (appendix). See README.md for the method.
"""

from collections import Counter
import json
from pathlib import Path
import re
import statistics
import sys

JS_LIBRARIES = ("sift", "mingo")
AREAS = ["equality", "range", "$in/$nin", "$all", "$elemMatch", "$size", "$exists", "$type",
         "$mod", "$regex", "logical"]
PATHS = ["top-level field", "dotted field", "numeric index", "noncanonical index", "empty component"]
OPERANDS = ["number", "NaN/inf", "string", "null", "bool", "binary", "date", "regex", "array", "document"]
SYMBOL = {"agrees": "✓", "differs": "≠", "error": "✗", "rejected by MongoDB": "—"}
OPERATIONS = ("match", "construct", "single-use")
# Representative workloads from benchmarks/cases.py, in table order.
WORKLOADS = [
    ("flat", "Flat equality, hit"), ("flat-miss", "Flat equality, miss"),
    ("deep", "Five-level path, hit"), ("subdocs-last", "`x.y` over 100 subdocuments, last hit"),
    ("subdocs-miss", "`x.y` over 100 subdocuments, miss"), ("indexed-eq", "Numeric index `a.9.x`"),
    ("in-1000-last", "`$in` of 1,000, last hit"), ("in-1000-miss", "`$in` of 1,000, miss"),
    ("regex", "`$regex` string"), ("regex-scan-last", "`$regex` over 100 strings, last hit"),
    ("and-or", "`$and` + `$or`"), ("and-hit", "`$and` of 100, all true"), ("or-miss", "`$or` of 100, none true"),
    ("wide-document-hit-10000", "10,000-field document, last field"),
    ("wide-document-miss-10000", "10,000-field document, absent field"),
    ("numeric-last", "`$gt` over 100 numbers, last hit"), ("all-number-98", "`$all` of two over 100 numbers"),
    ("elem-match-value", "`$elemMatch` value range over 100"),
    ("elem-document-last", "`$elemMatch` document, last of 100"),
    ("size", "`$size`"), ("mod", "`$mod`"), ("path-exists-99", "`x.y` `$exists`, last of 100"),
    ("document-scan-last", "Embedded document equality, last of 100"),
    ("missing-null", "`{a.b.c: null}` on `{}`"),
]
# Factual notes; each claim is checked against the tables below.
NOTES = {
    "mgqpy": "Second to tinymongo on the new queries and the MongoDB manual examples; highest on the full "
             "corpus, which it was developed against. No `$type`, `$comment`, `$expr`, `$jsonSchema` or bitwise operators. "
             "Regex uses Python `re`, so `\\w` matches Unicode letters and PCRE-only syntax such as `(?-i)` is "
             "rejected. Fastest Python matcher on most timed cases, but construction compiles the whole query, so single "
             "use is slower than libraries that interpret the filter directly.",
    "mongomock": "No `$mod`; `$type` codes are rejected but aliases work. Embedded-document equality ignores "
                 "key order (MongoDB compares it). Much faster than mgqpy for embedded-document equality "
                 "and faster for single use on about half the cases; no separate construction step.",
    "mongoquery": "Targets MongoDB 3.4 semantics. Raises `TypeError` on many mixed-type comparisons and "
                  "accepts most invalid queries. Construction only stores the query, so it is the fastest "
                  "to construct and often faster for single use.",
    "mongo-query-match": "Fork of mongoquery with the same behaviour on this corpus (one query differs).",
    "montydb": "Supports `$type` and `$mod`; differs from MongoDB on NaN, `$exists` with non-boolean "
               "values and empty path components. Slowest Python matcher here.",
    "tinymongo": "Most compatible on the new queries and the MongoDB manual examples, including `$type`; "
                 "rejects nearly every query MongoDB rejects and raised on one valid query (PCRE `(?-i)`). Slower than "
                 "mgqpy at matching on almost every case.",
    "mongita": "Supports only `$eq`, `$ne`, `$in`, `$nin`, `$gt`, `$gte`, `$lt`, `$lte` and implicit "
               "equality on fields; `$and`/`$or`/`$nor` are treated as field names. Fast where it is correct, "
               "because it does little work.",
}


def load(path):
    return json.loads(path.read_text()) if path.exists() else None


def fmt(us):
    return "" if us is None else f"{us:,.2f}" if us < 10 else f"{us:,.1f}" if us < 1000 else f"{us:,.0f}"


def header(names, align="---:"):
    return "| | " + " | ".join(names) + " |\n| --- |" + f" {align} |" * len(names)


def agree_cell(counter):
    n = sum(counter.get(k, 0) for k in ("agree", "mismatch", "error"))
    return "–" if not n else f"{counter.get('agree', 0)}/{n}"


def compat_tables(c, libs, out, headline=True):
    s = c["summary"]
    docs = s["docs"]
    groups = [g for g in docs[libs[0]]["groups"] if g != "total"]
    if headline:
        out.append("| Query set | " + " | ".join(libs) + " |\n| --- |" + " ---: |" * len(libs))
        out.append(f"| **New queries** ({c['corpus']['by_origin']['new']}) | " + " | ".join(
            agree_cell(s["libraries"][lib]["areas"]["origin: new"]) for lib in libs) + " |")
        out.append(f"| **MongoDB manual examples** ({sum(docs[libs[0]]['groups']['total'].values())}) | "
                   + " | ".join(agree_cell(docs[lib]["groups"]["total"]) for lib in libs) + " |")
        out.append("| Full corpus, incl. probe | "
                   + " | ".join(agree_cell(s["libraries"][lib]["areas"]["total"]) for lib in libs) + " |")
        out.append("| Rejects what MongoDB rejects | " + " | ".join(
            f"{s['libraries'][lib]['areas'].get('error behaviour', {}).get('rejects', 0)}/"
            f"{sum(s['libraries'][lib]['areas'].get('error behaviour', {}).values())}" for lib in libs) + " |")
        out.append("")

    out.append("#### Operator coverage\n\n✓ agrees with MongoDB on one canonical query, ≠ runs but returns a "
               "different set, ✗ raises (unsupported or crashes).\n")
    out.append(header(libs, ":---:").replace("| |", "| Operator |", 1))
    for label in s["coverage"][libs[0]]:
        out.append(f"| {label} | " + " | ".join(SYMBOL[s["coverage"][lib][label]] for lib in libs) + " |")
    out.append("")

    out.append("#### MongoDB manual examples by page\n")
    out.append(header(libs).replace("| |", "| Page |", 1))
    for group in groups:
        out.append(f"| {group} | " + " | ".join(agree_cell(docs[lib]["groups"].get(group, {})) for lib in libs) + " |")
    out.append("")

    def table(title, keys, prefix):
        out.append(f"#### {title}\n\nFull corpus: agreeing / server-accepted queries.\n")
        out.append(header(libs))
        for key in keys:
            out.append(f"| {key} | " + " | ".join(agree_cell(s["libraries"][lib]["areas"].get(prefix + key, {}))
                                                  for lib in libs) + " |")
        out.append("")

    table("By operator", AREAS, "area: ")
    table("By path shape (dotted and numeric paths, array traversal)", PATHS, "path: ")
    table("By operand type, for equality, ranges, `$in`/`$nin` and `$all` (type handling, BSON order)",
          OPERANDS, "operand: ")
    out.append("#### Wrong answers and exceptions\n")
    out.append(header(libs))
    for label, key in (("Wrong answer", "mismatch"), ("Raises on a valid query", "error")):
        out.append(f"| {label} | " + " | ".join(str(s["libraries"][lib]["areas"]["total"].get(key, 0))
                                                for lib in libs) + " |")
    out.append("")
    for lib in libs:
        errors = Counter(s["libraries"][lib]["exceptions"])
        out.append(f"- **{lib}**: " + (", ".join(f"{k} ×{v}" for k, v in errors.most_common(5)) or "none"))
    out.append("")
    out.append("#### Examples\n\nFirst disagreement per area in the full corpus, and every miss on the MongoDB "
               "manual examples.\n")
    for lib in libs:
        out.append(f"<details><summary>{lib}</summary>\n")
        for key in ["area: " + a for a in AREAS] + ["error behaviour"]:
            for example in s["libraries"][lib]["examples"].get(key, [])[:1]:
                text = f"`{example['query']}`: {example['outcome']}"
                if "documents" in example:
                    d = example["documents"][0]
                    text += (f"; on `{d['document']}` MongoDB {'matches' if d['mongodb'] else 'does not match'}, "
                             f"library {'matches' if d['library'] else 'does not'} "
                             f"({example['differing_documents']} documents differ)")
                elif "error" in example:
                    text += f"; {example['error']['type']}: {example['error']['message'][:100]}"
                else:
                    text += f"; MongoDB: {example['mongodb']['message'][:80]}"
                out.append(f"- {key}: {text}")
        for miss in docs[lib]["misses"]:
            out.append(f"- manual, [{miss['group']}]({miss['url']}): `{miss['query']}`: {miss['outcome']}; "
                       f"MongoDB {miss['mongodb']}, library {miss['library']}")
        out.append("\n</details>\n")


def family(name):
    """Hit/miss variants of one workload, e.g. or-early/or-last/or-miss, path-eq-0/99/None."""
    return re.sub(r"-(early|last|miss|hit|0|98|99|None)$", "", name)


def counted(p):
    """Time a case for a library only if it answers the case's whole hit/miss family correctly.

    A library that skips the work can return the right bool on a miss for the wrong
    reason (mongita treats `$or` as a field name, so every `$or` misses).
    """
    failed = {(family(r["name"]), n) for r in p["results"] if r["server"] == "agrees"
              for n, st in r["status"].items() if not st["eligible"]}
    return lambda r, n: r["status"][n]["eligible"] and (family(r["name"]), n) not in failed


def ratio_summary(p, baseline, names, out):
    ok = counted(p)
    eligible = Counter(n for r in p["results"] for n, st in r["status"].items() if st["eligible"])
    timed = Counter(n for r in p["results"] for n in r["status"] if ok(r, n))
    out.append(header(names))
    out.append("| Correct answer (MongoDB and library agree) | " + " | ".join(str(eligible[n]) for n in names) + " |")
    out.append("| Timed: whole hit/miss family correct | " + " | ".join(str(timed[n]) for n in names) + " |")
    for operation in OPERATIONS:
        ratios = {n: [] for n in names}
        for r in p["results"]:
            for n, ratio in r["timings"].get(operation, {}).get(f"paired_ratio_to_{baseline}", {}).items():
                if n in ratios and ok(r, n) and ok(r, baseline):
                    ratios[n].append(ratio)
        out.append(f"| {operation}: median ratio to {baseline} (min–max) | " + " | ".join(
            "1" if n == baseline else (f"{statistics.median(ratios[n]):.2f}× "
                                       f"({min(ratios[n]):.2f}–{max(ratios[n]):.2f})" if ratios[n] else "–")
            for n in names) + " |")
        out.append(f"| {operation}: cases faster than {baseline} | " + " | ".join(
            "" if n == baseline else f"{sum(x < 1 for x in ratios[n])}/{len(ratios[n])}" for n in names) + " |")
    controls = {op: [r["timings"][op][f"paired_ratio_to_{baseline}"]["control"] for r in p["results"]
                     if "control" in r["timings"].get(op, {}).get(f"paired_ratio_to_{baseline}", {})]
                for op in OPERATIONS}
    out.append("\nIdentical-source control range (same library imported twice): " + "; ".join(
        f"{op} {min(v):.3f}–{max(v):.3f}×" for op, v in controls.items() if v) + ".\n")


def workload_tables(p, baseline, names, out):
    ok = counted(p)
    by_name = {r["name"]: r for r in p["results"]}
    for operation in ("match", "single-use"):
        out.append(f"#### {operation.capitalize()}: median µs per call (paired ratio to {baseline})\n\n"
                   "Blank: wrong answer in the case or its hit/miss family.\n")
        out.append(header(names).replace("| |", "| Workload |", 1))
        for case, label in WORKLOADS:
            r = by_name.get(case)
            if not r or operation not in r["timings"]:
                continue
            t = r["timings"][operation]
            cells = []
            for n in names:
                if not ok(r, n) or n not in t["median_us"]:
                    cells.append("")
                elif n == baseline:
                    cells.append(fmt(t["median_us"][n]))
                else:
                    cells.append(f"{fmt(t['median_us'][n])} ({t[f'paired_ratio_to_{baseline}'][n]:.2f}×)")
            out.append(f"| {label} | " + " | ".join(cells) + " |")
        out.append("")


def run_facts(p, runtime):
    hw = p["hardware"]
    return (f"Measured {p['started_utc'][:10]} with {runtime}, {hw['cpu_model']}, {hw['logical_cpus']} logical "
            f"CPUs, {hw['physical_memory_bytes'] / 2**30:.1f} GiB, {hw['os']}, MongoDB "
            f"{', '.join(p['mongodb_versions'])} for ground truth. Comparisons are valid only within one run on "
            "one machine.\n")


def main():
    directory = Path(sys.argv[1])
    c = load(directory / "compat.json")
    p = load(directory / "perf.json")
    j = load(directory / "perf-js.json")
    checks = sorted(directory.glob("perf-3.*.json"))
    py_libs = [n for n in c["libraries"] if n not in JS_LIBRARIES]
    servers = ", ".join(v["version"] for v in c["servers"].values())
    out = ["# mgqpy compared with other offline MongoDB filter matchers\n",
           "Generated by [`report.py`](../report.py) from the JSON in this directory. Method, library selection "
           "and rerun instructions: [README.md](../README.md). JavaScript libraries are in the "
           "[appendix](#appendix-javascript-sift-and-mingo).\n"]

    out.append("## Libraries\n")
    out.append("| Library | Version | Entry point | Notes |\n| --- | --- | --- | --- |")
    for name in py_libs:
        lib = c["libraries"][name]
        out.append(f"| {name} | {lib['version']} | `{lib['entry_point']}` | {NOTES[name]} |")
    out.append("")

    out.append("## Compatibility with MongoDB\n")
    out.append(f"Ground truth: `find` on MongoDB {servers}; the servers agree on every query (rejection messages "
               "differ between versions, codes do not). A query agrees only if the library returns exactly the "
               "server's set of matching documents; one wrong document or one exception counts as a "
               "disagreement. Three query sets:\n")
    out.append(f"- **New queries**: {c['corpus']['by_origin']['new']} queries written for this comparison and not "
               "used to develop any library. Headline.\n"
               "- **MongoDB manual examples**: the filters and sample documents from the MongoDB manual's query "
               "tutorials and operator pages ([`corpus_docs.py`](../corpus_docs.py) links each page). "
               "Independent of everyone here.\n"
               f"- **Full corpus**: adds {c['corpus']['by_origin']['probe']} queries from the real-server "
               "differential that mgqpy 1.0.2 was developed against, so mgqpy's result on it is expected, not "
               f"independent. {c['corpus']['documents']} documents in all. Also "
               f"{c['corpus']['by_origin']['invalid']} queries MongoDB rejects, for error behaviour.\n")
    compat_tables(c, py_libs, out)

    if p:
        names = [n for n in p["results"][0]["status"] if n != "control"]
        out.append(f"## Performance (CPython {p['python'].split()[0]})\n")
        out.append(run_facts(p, f"CPython {p['python'].split()[0]}"))
        excluded = Counter(r["server"].split(":")[0] for r in p["results"] if r["server"] != "agrees")
        out.append(f"Cases: the {len(p['results'])} workloads in [`benchmarks/cases.py`](../../cases.py), timed with "
                   "the paired method of [`benchmarks/run.py`](../../run.py): two fresh processes with alternating "
                   "import order, 12 shuffled paired blocks each, 5 ms CPU target for the slowest variant, GC off "
                   "while timing, pinned CPU. Ratios are medians of the 24 paired block ratios, library / mgqpy; "
                   "lower is faster. `match` reuses each library's prepared object (mongomock has none and "
                   "interprets the filter on every call); `construct` is the preparation step; `single-use` is "
                   "both. Excluded for every library because MongoDB cannot answer them comparably: "
                   + "; ".join(f"{v} × {k}" for k, v in excluded.items()) + ". A library is timed only on cases "
                   "where it returns MongoDB's answer for the case and its hit/miss siblings.\n")
        ratio_summary(p, "mgqpy", names, out)
        workload_tables(p, "mgqpy", names, out)
        for path in checks:
            check = load(path)
            version = check["python"].split()[0]
            out.append(f"### Check: CPython {version}\n\n" + run_facts(check, f"CPython {version}"))
            ratio_summary(check, "mgqpy", [n for n in check["results"][0]["status"] if n != "control"], out)

    js_libs = [n for n in c["libraries"] if n in JS_LIBRARIES]
    if js_libs:
        out.append("## Appendix: JavaScript (sift and mingo)\n")
        out.append("| Library | Version | Entry point |\n| --- | --- | --- |")
        for name in js_libs:
            out.append(f"| {name} (npm) | {c['libraries'][name]['version']} | `{c['libraries'][name]['entry_point']}` |")
        out.append("")
        out.append("### Compatibility\n\nSame corpus and ground truth, run in Node by "
                   "[`js/compat.mjs`](../js/compat.mjs). Values that JavaScript cannot represent unchanged "
                   "(integers beyond 2⁵³, verbose regexes, objects whose integer-like keys JavaScript reorders) "
                   f"are excluded: {c['summary']['libraries'][js_libs[0]]['areas'].get('not representable', {}).get('n/a', 0)} "
                   f"queries and {len(c['libraries'][js_libs[0]]['excluded_documents'])} documents. mgqpy is "
                   "repeated for reference.\n")
        compat_tables(c, ["mgqpy"] + js_libs, out)
    if j:
        out.append(f"### Performance (Node {j['node']})\n")
        out.append(run_facts(j, f"Node {j['node']}"))
        out.append("Same cases, eligibility rule, calibration and block structure as the Python run, implemented "
                   "in [`js/perf.mjs`](../js/perf.mjs): `process.cpuUsage` timer, JIT-compiled code after 100 "
                   "warm-up calls, `gc()` between blocks (GC cannot be disabled while timing). sift is the "
                   "baseline; a second, independently loaded sift module is the control. "
                   f"{len(j['unrepresentable_cases'])} cases use Python-only values and are not exported. The "
                   "µs are not comparable with the Python tables: different runtimes, timers and value "
                   "representations, and the runs were not paired.\n")
        ratio_summary(j, "sift", ["sift", "mingo"], out)
        workload_tables(j, "sift", ["sift", "mingo"], out)
    (directory / "RESULTS.md").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
