#!/usr/bin/env python3
"""Differential of offline MongoDB-filter matchers against real MongoDB servers.

    python benchmarks/compare/compat.py --ports 27017 27018 --output results/compat.json

Every corpus query runs on each server (`find` over the inserted corpus) and in
each library, one subprocess per library. See README.md.
"""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
import pickle
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from corpus import COVERAGE, COVERAGE_DOCUMENTS, classify, documents, queries  # noqa: E402
import adapters  # noqa: E402
from corpus_docs import groups as docs_groups  # noqa: E402

JS = HERE / "js"
JS_LIBRARIES = ("sift", "mingo")


class Unrepresentable(Exception):
    pass


def js_encode(value):
    """Tagged JSON for js/compat.mjs; raise when JavaScript would change the value."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        if abs(value) > 2 ** 53:
            raise Unrepresentable("integer beyond 2**53")
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else {"$$f": str(value).replace("inf", "Infinity").replace("nan", "NaN")}
    if isinstance(value, bytes):
        return {"$$bytes": value.hex()}
    if isinstance(value, datetime):
        return {"$$date": int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)}
    if isinstance(value, re.Pattern):
        if value.flags & re.X:
            raise Unrepresentable("verbose regex")
        flags = "".join(f for f, bit in (("i", re.I), ("m", re.M), ("s", re.S)) if value.flags & bit)
        return {"$$re": [value.pattern, flags]}
    if isinstance(value, list):
        return [js_encode(v) for v in value]
    if isinstance(value, dict):
        keys = list(value)
        index = sorted((k for k in keys if k.isdigit() and (k == "0" or k[0] != "0") and int(k) < 2 ** 32 - 1),
                       key=int)
        if index + [k for k in keys if k not in index] != keys:
            raise Unrepresentable("JavaScript reorders integer-like keys")
        return {k: js_encode(v) for k, v in value.items()}
    raise Unrepresentable(type(value).__name__)


def js_outcomes(output):
    def encode(value):
        try:
            return js_encode(value)
        except Unrepresentable:
            return None
    docs = [encode(d) for d in documents()]
    corpus = {"documents": docs, "queries": [encode(q) for _, q in queries()],
              "coverage_documents": [encode(d) for d in COVERAGE_DOCUMENTS],
              "coverage": [encode(q) for _, q in COVERAGE],
              "docs": [{"documents": [encode(d) for d in group_docs], "queries": [encode(q) for q in group_queries]}
                       for _, _, group_docs, group_queries in docs_groups()]}
    path = output.with_name(output.stem + ".js-corpus.json")
    result = output.with_name(output.stem + ".js-results.json")
    path.write_text(json.dumps(corpus, allow_nan=False))
    subprocess.run(["node", str(JS / "compat.mjs"), str(path), str(result)], check=True)
    out = json.loads(result.read_text())
    path.unlink()
    result.unlink()
    excluded = [i for i, d in enumerate(docs) if d is None]
    for name, lib in out.items():
        lib["version"] = json.loads((JS / "node_modules" / name / "package.json").read_text())["version"]
        lib["entry_point"] = {"sift": "sift(q)(d)", "mingo": "new mingo.Query(q).test(d)"}[name]
        lib["excluded_documents"] = excluded
        lib["node"] = subprocess.check_output(["node", "--version"], text=True).strip()
    return out


def server_truth(port):
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure
    docs, rows = documents(), queries()
    client = MongoClient(port=port, serverSelectionTimeoutMS=3000)
    db = client["offline_compare_" + uuid4().hex]
    try:
        db.c.insert_many([dict(doc, _id=i) for i, doc in enumerate(docs)])
        results = []
        for _, query in rows:
            try:
                results.append(sorted(d["_id"] for d in db.c.find(query, {"_id": 1})))
            except OperationFailure as error:
                results.append({"rejected": error.code, "message": str(error).split(", full error")[0]})
        db.cov.insert_many([dict(doc, _id=i) for i, doc in enumerate(COVERAGE_DOCUMENTS)])
        coverage = []
        for _, query in COVERAGE:
            try:
                coverage.append(sorted(d["_id"] for d in db.cov.find(query, {"_id": 1})))
            except OperationFailure as error:
                coverage.append({"rejected": error.code, "message": str(error).split(", full error")[0]})
        docs_results = []
        for g, (_, _, group_docs, group_queries) in enumerate(docs_groups()):
            coll = db[f"docs{g}"]
            coll.insert_many([dict(doc, _id=i) for i, doc in enumerate(deepcopy(group_docs))])
            for query in group_queries:
                try:
                    docs_results.append(sorted(d["_id"] for d in coll.find(query, {"_id": 1})))
                except OperationFailure as error:
                    docs_results.append({"rejected": error.code, "message": str(error).split(", full error")[0]})
        return {"version": client.server_info()["version"], "results": results, "coverage": coverage,
                "docs": docs_results}
    finally:
        client.drop_database(db.name)
        client.close()


def library_outcomes(name):
    prepare, match, entry = adapters.LIBRARIES[name][1]()
    started = time.process_time()
    docs = deepcopy(documents())
    pristine = pickle.dumps(docs)
    results, non_bool = evaluate(prepare, match, [q for _, q in queries()], docs)
    cpu = time.process_time() - started
    coverage, _ = evaluate(prepare, match, [q for _, q in COVERAGE], deepcopy(COVERAGE_DOCUMENTS))
    docs_results = []
    for _, _, group_docs, group_queries in docs_groups():
        docs_results += evaluate(prepare, match, group_queries, deepcopy(group_docs))[0]
    return {"version": adapters.version(name), "entry_point": entry, "results": results,
            "coverage": coverage, "docs": docs_results, "non_bool_returns": non_bool,
            "documents_mutated": pickle.dumps(docs) != pristine, "cpu_seconds": cpu}


def evaluate(prepare, match, query_list, docs):
    results = []
    non_bool = 0
    for query in query_list:
        q = deepcopy(query)
        try:
            prepared = prepare(q)
        except Exception as error:
            results.append({"error": "construct", "type": type(error).__name__, "message": str(error)[:200]})
            continue
        hits = []
        try:
            for i, doc in enumerate(docs):
                value = match(prepared, doc)
                if type(value) is not bool:
                    non_bool += 1
                if value:
                    hits.append(i)
        except Exception as error:
            results.append({"error": "match", "type": type(error).__name__,
                            "message": str(error)[:200], "document": i})
            continue
        results.append(hits)
    return results, non_bool


def summarize(data):
    rows = queries()
    docs = documents()
    truth_ports = list(data["servers"])
    def outcome(result):  # Rejection messages differ between versions; codes do not.
        return {"rejected": result["rejected"]} if isinstance(result, dict) else result

    reference = data["servers"][truth_ports[0]]["results"]
    server_disagreements = [i for i in range(len(rows)) if any(
        outcome(data["servers"][p]["results"][i]) != outcome(reference[i]) for p in truth_ports)]
    summary = {"server_disagreements": [repr(rows[i][1]) for i in server_disagreements], "libraries": {},
               "coverage": {}}
    for name, lib in data["libraries"].items():
        cells = {}
        for (label, _), expected, actual in zip(COVERAGE, data["servers"][truth_ports[0]]["coverage"],
                                                lib["coverage"]):
            if isinstance(expected, dict):
                cells[label] = "rejected by MongoDB"
            elif isinstance(actual, dict):
                cells[label] = "error"
            else:
                cells[label] = "agrees" if actual == expected else "differs"
        summary["coverage"][name] = cells
    summary["docs"] = {}
    summary["docs_server_disagreements"] = [i for i, r in enumerate(data["servers"][truth_ports[0]]["docs"]) if any(
        outcome(data["servers"][p]["docs"][i]) != outcome(r) for p in truth_ports)]
    flat = [(label, url, q) for label, url, _, qs in docs_groups() for q in qs]
    for name, lib in data["libraries"].items():
        groups = defaultdict(Counter)
        misses = []
        for (label, url, query), expected, actual in zip(flat, data["servers"][truth_ports[0]]["docs"], lib["docs"]):
            if isinstance(expected, dict):
                key = "rejects" if isinstance(actual, dict) else "accepts invalid"
            elif actual == "n/a":
                key = "n/a"
            elif isinstance(actual, dict):
                key = "error"
            else:
                key = "agree" if actual == expected else "mismatch"
            groups[label][key] += 1
            groups["total"][key] += 1
            if key in ("error", "mismatch", "accepts invalid"):
                misses.append({"group": label, "url": url, "query": repr(query), "outcome": key,
                               "mongodb": expected if isinstance(expected, list) else "rejected",
                               "library": actual if isinstance(actual, list) else
                               f"{actual['type']}: {actual['message'][:100]}" if isinstance(actual, dict) else actual})
        summary["docs"][name] = {"groups": {k: dict(v) for k, v in groups.items()}, "misses": misses}
    for name, lib in data["libraries"].items():
        areas = defaultdict(Counter)
        examples = defaultdict(list)
        excluded = set(lib.get("excluded_documents", ()))
        for i, ((origin, query), expected, actual) in enumerate(zip(rows, reference, lib["results"])):
            if i in server_disagreements:
                continue
            if actual == "n/a":
                areas["not representable"]["n/a"] += 1
                continue
            if excluded and isinstance(expected, list):
                expected = [d for d in expected if d not in excluded]
            area, path_class, operand = classify(query)
            if isinstance(expected, dict):
                outcome = ("rejects" if isinstance(actual, dict) else "accepts invalid")
                keys = ["error behaviour"]
            else:
                if isinstance(actual, dict):
                    outcome = "error"
                elif actual == expected:
                    outcome = "agree"
                else:
                    outcome = "mismatch"
                keys = ["area: " + area, "path: " + path_class, "origin: " + origin]
                if area in ("equality", "range", "$in/$nin", "$all"):
                    keys.append("operand: " + operand)
            for key in keys + ["total"]:
                areas[key][outcome] += 1
            if outcome in ("mismatch", "error", "accepts invalid"):
                for key in keys:
                    if len(examples[key]) < 3:
                        example = {"query": repr(query), "outcome": outcome}
                        if outcome == "mismatch":
                            diff = sorted(set(actual) ^ set(expected))
                            example["documents"] = [
                                {"document": repr(docs[d]), "mongodb": d in expected, "library": d in actual}
                                for d in diff[:2]]
                            example["differing_documents"] = len(diff)
                        elif outcome == "error":
                            example["error"] = actual
                        else:
                            example["mongodb"] = expected
                            example["library_matches"] = len(actual) if isinstance(actual, list) else actual
                        examples[key].append(example)
        exceptions = Counter(f"{r['error']} {r['type']}" for r in lib["results"] if isinstance(r, dict))
        summary["libraries"][name] = {"areas": {k: dict(v) for k, v in sorted(areas.items())},
                                      "examples": dict(examples), "exceptions": dict(exceptions.most_common())}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ports", nargs="+", type=int, default=[27017])
    parser.add_argument("--libraries", nargs="+", default=[*adapters.LIBRARIES, *JS_LIBRARIES])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.worker:
        args.output.write_text(json.dumps(library_outcomes(args.worker)))
        return 0
    rows = queries()
    data = {"python": sys.version, "platform": platform.platform(),
            "corpus": {"documents": len(documents()), "queries": len(rows),
                       "by_origin": dict(Counter(origin for origin, _ in rows))},
            "servers": {}, "libraries": {}}
    for port in args.ports:
        print("server", port, flush=True)
        data["servers"][str(port)] = server_truth(port)
    if any(name in JS_LIBRARIES for name in args.libraries):
        print("JavaScript libraries", flush=True)
        js = js_outcomes(args.output)
    for name in args.libraries:
        if name in JS_LIBRARIES:
            data["libraries"][name] = js[name]
            continue
        print("library", name, flush=True)
        part = args.output.with_name(args.output.stem + f".{name}.part.json")
        subprocess.run([sys.executable, __file__, "--worker", name, "--output", str(part)], check=True)
        data["libraries"][name] = json.loads(part.read_text())
        part.unlink()
    data["summary"] = summarize(data)
    args.output.write_text(json.dumps(data, separators=(",", ":")))
    for name, lib in data["summary"]["libraries"].items():
        print(name, lib["areas"]["total"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
