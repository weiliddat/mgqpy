"""Print snapshot tables; --write updates README.md, --check detects stale tables."""

import argparse
import json
from pathlib import Path
import re


MATCHING = [
    ("indexed-miss", "Numeric-index miss"),
    ("path-exists-99", "`$exists` over subdocuments, last hit"),
    ("subdocs-last", "Subdocument field, last hit"),
    ("document-scan-last", "Flat-document equality, last hit"),
    ("path-in-99", "Path `$in` of two, last hit"),
    ("in-1000-last", "`$in`, last of 1,000"),
    ("all-singleton-array-99", "Singleton array `$all`, last hit"),
    ("all-singleton-document-99", "Singleton document `$all`, last hit"),
    ("value-document-99", "Ordered-document equality, last hit"),
]
CONSTRUCTION = [
    ("flat", "Flat equality"),
    ("and-early", "100-clause `$and`"),
    ("construct-and-10000", "10,000-clause `$and`"),
    ("in-1000-last", "`$in` of 1,000"),
    ("construct-in-10000", "`$in` of 10,000"),
    ("implicit-regex-early", "Compiled regex"),
    ("regex", "`$regex` string"),
]


def span(values, ratio=True):
    numbers = [f"{v:.3f}" if ratio or v < 100 else f"{v:,.0f}" for v in (min(values), max(values))]
    return (numbers[0] if ratio and numbers[0] == numbers[1] else "–".join(numbers)) + ("×" if ratio else "")


def tables(here):
    data = [json.loads(p.read_text(encoding="utf-8")) for p in (here / "snapshot").glob("*.json")]
    if not data:
        raise ValueError("no snapshot JSON files")
    data.sort(key=lambda d: tuple(map(int, d["python"].split(".")[:2])))
    if len(data[0]["refs"]) != 3 or any(list(d["refs"].items()) != list(data[0]["refs"].items()) for d in data):
        raise ValueError("snapshot files must compare the same three refs in the same order")
    first, previous, last = data[0]["refs"]
    old, prev, new = [ref["label"] for ref in data[0]["refs"].values()]
    comparison = f"{new} / {prev}"
    pythons = ["Python " + ".".join(d["python"].split(".")[:2]) for d in data]
    if len(set(pythons)) != len(pythons):
        raise ValueError("snapshot must contain one file per Python major.minor version")
    rows = [{r["name"]: r for r in d["results"]} for d in data]
    if any(set(r) != set(rows[0]) or len(r) != len(d["results"]) for r, d in zip(rows, data)):
        raise ValueError("snapshot files have missing, extra or duplicate case names")
    result = {}

    def table(name, header, body):
        result[name] = "\n".join("| " + " | ".join(map(str, row)) + " |" for row in
                                 [header, ["---"] + ["---:"] * (len(header) - 1), *body])

    table("controls", ["CPython", f"Eligible against {old}, of {len(rows[0])}",
                       "Identical-source matching", "Construction", "Single use"], [
        [d["python"].split()[0], sum(r["status"][first]["eligible"] and r["status"][last]["eligible"]
                                    for r in d["results"])] +
        [span([r["timings"][op]["paired_ratio"]["control"] for r in d["results"]])
         for op in ("match", "construct", "single-use")] for d in data])
    for name, op, cases in (("matching", "match", MATCHING), ("construction", "construct", CONSTRUCTION),
                            ("single-use", "single-use", [CONSTRUCTION[0], MATCHING[0], *MATCHING[5:8]])):
        body = []
        for case, label in cases:
            timings = [r[case]["timings"][op] for r in rows]
            values = ([f'{t["paired_ratio_to_previous"]:.3f}×' for t in timings] if op == "match" else
                      [span([t["median_us"][slot] for t in timings], False) for slot in (first, previous, last)])
            ratios = ([span([t["paired_ratio"][slot] for t in timings]) for slot in (previous, last)]
                      if op == "match" else [span([t["paired_ratio_to_previous"] for t in timings])])
            if op == "single-use":
                ratios.append(span([t["paired_ratio"][last] for t in timings]))
            body.append([label, *values, *ratios])
        header = ([f"Matching, {comparison}", *pythons, f"{prev} / {old}", f"{new} / {old}"] if op == "match" else
                  ["Construction" if op == "construct" else "Single use", *[f"{v} (µs)" for v in (old, prev, new)], comparison])
        table(name, header + ([f"{new} / {old}"] if op == "single-use" else []), body)
    table("slower", ["Case / operation", *pythons], [
        [f"`{case}` / {op}", *[f"{v:.3f}×" for v in values]]
        for case in sorted(rows[0]) for op in ("match", "construct", "single-use")
        for values in [[r[case]["timings"][op]["paired_ratio_to_previous"] for r in rows]] if max(values) > 1.03])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="replace only generated README table contents")
    mode.add_argument("--check", action="store_true", help="exit 1 if generated README tables are stale")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    try:
        generated = tables(here)
    except (KeyError, ValueError, OSError) as error:
        parser.error(f"Invalid snapshot: {error}")
    if args.write or args.check:
        readme = here / "README.md"
        original = updated = readme.read_text(encoding="utf-8")
        markers = re.findall(r"<!-- (BEGIN|END) generated: (.*?) -->", original)
        if (sorted(markers[::2]) != sorted(("BEGIN", name) for name in generated)
                or markers[1::2] != [("END", name) for _, name in markers[::2]]):
            parser.error("README markers must form exactly one non-nested BEGIN/END pair per table: "
                         + ", ".join(generated))
        for name, table in generated.items():
            begin, end = f"<!-- BEGIN generated: {name} -->", f"<!-- END generated: {name} -->"
            before, rest = updated.split(begin)
            _, after = rest.split(end)
            updated = before + begin + "\n" + table + "\n" + end + after
        if args.check:
            if original != updated:
                parser.exit(1, "Snapshot tables differ; run python benchmarks/report.py --write and review the diff.\n")
        else:
            readme.write_text(updated, encoding="utf-8")
    else:
        print("\n\n".join(generated.values()))
