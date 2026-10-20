#!/usr/bin/env python3
"""Time offline matchers on benchmarks/cases.py with run.py's paired method.

    python benchmarks/compare/perf.py --ports 27017 27018 --output results/perf.json

A case is timed for a library only if real MongoDB returns the case's literal
expected boolean on every server and the library returns that same bool.
mgqpy is the baseline; a second independent mgqpy import is the identical-source
control. See README.md.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pickle
import platform
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import run  # noqa: E402  (benchmarks/run.py: measure, load, activate, hardware)
from cases import cases  # noqa: E402
import adapters  # noqa: E402

OPERATIONS = ("match", "construct", "single-use")
DEFAULT = ["mgqpy", "mongomock", "mongoquery", "mongo-query-match", "montydb", "tinymongo", "mongita"]


def server_truth(ports, filters):
    """Per case: True/False from every server, or the reason it is not comparable."""
    from bson.errors import InvalidDocument
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure
    from uuid import uuid4
    out = {}
    for port in ports:
        client = MongoClient(port=port, serverSelectionTimeoutMS=3000)
        version = client.server_info()["version"]
        db = client["offline_perf_" + uuid4().hex]
        try:
            for index, (name, query, document, expected) in cases(filters):
                coll = db[f"c{index}"]
                try:
                    coll.insert_one(dict(document, _id=0))
                    found = coll.count_documents(query) == 1
                    result = "agrees" if found is expected else f"MongoDB {version} returns {found}"
                except (InvalidDocument, OverflowError, ValueError) as error:
                    result = f"not BSON-encodable: {type(error).__name__}: {str(error)[:80]}"
                except OperationFailure as error:
                    result = f"rejected by MongoDB {version}: {error.code}"
                previous = out.get(name)
                out[name] = result if previous in (None, "agrees") else previous
                coll.drop()
        finally:
            client.drop_database(db.name)
            client.close()
        out.setdefault("__versions__", []).append(version)
    return out


def check(prepare, match, query, document, expected):
    try:
        prepared = prepare(query)
    except Exception as error:
        return {"outcome": run.error_outcome("construct", error), "eligible": False}, None
    try:
        actual = match(prepared, document)
        outcome = {"phase": "match", "type": type(actual).__name__, "value": repr(actual)}
        correct = type(actual) is bool and actual is expected
    except Exception as error:
        outcome, correct = run.error_outcome("match", error), False
    return {"outcome": outcome, "eligible": correct}, prepared


def worker(config, reverse):
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        affinity = min(os.sched_getaffinity(0)) if config["cpu"] is None else config["cpu"]
        os.sched_setaffinity(0, {affinity})
    names = list(config["libraries"])
    order = list(reversed(names)) if reverse else names
    # Two independent mgqpy imports (baseline and control) via run.py's loader.
    packages, entries = {}, {}
    for name in order:
        if name == "mgqpy":
            for slot in ("mgqpy", "control"):
                packages[slot] = run.load(adapters.ROOT)
        else:
            packages[name] = {}
            prepare, match, _ = adapters.LIBRARIES[name][1]()
            entries[name] = (prepare, match)
    for slot in ("mgqpy", "control"):
        with run.activate(packages[slot]):
            entries[slot] = (packages[slot]["mgqpy"].Query, lambda p, d: p.test(d))
    slots = ["mgqpy", "control"] + [n for n in names if n != "mgqpy"]
    rows = []
    for index, (name, query, document, expected) in cases(config["cases"]):
        pristine = pickle.dumps((query, document))
        inputs = {slot: deepcopy((query, document)) for slot in slots}
        statuses, prepared = {}, {}
        server_ok = config["truth"].get(name) == "agrees"
        for slot in slots:
            with run.activate(packages[slot]):
                statuses[slot], prepared[slot] = check(*entries[slot], *inputs[slot], expected)
            statuses[slot]["eligible"] = statuses[slot]["eligible"] and server_ok
        row = {"name": name, "expected": expected, "server": config["truth"].get(name),
               "status": statuses, "timings": {}}
        if server_ok and statuses["mgqpy"]["eligible"]:
            for operation in config["operations"]:
                functions = {}
                for slot in slots:
                    if not statuses[slot]["eligible"]:
                        continue
                    prep, match = entries[slot]
                    q, d, p = *inputs[slot], prepared[slot]
                    if operation == "match":
                        functions[slot] = lambda match=match, p=p, d=d: match(p, d)
                    elif operation == "construct":
                        if slot in ("mgqpy", "control") or adapters.LIBRARIES[slot][2]:
                            functions[slot] = lambda prep=prep, q=q: prep(q)
                    else:
                        functions[slot] = lambda prep=prep, match=match, q=q, d=d: match(prep(q), d)
                seed = 4361 + index + 1000 * OPERATIONS.index(operation)
                row["timings"][operation] = run.measure(
                    functions, seed, config, None if operation == "construct" else expected, packages)
        for slot in slots:
            assert pickle.dumps(inputs[slot]) == pristine, (name, slot, "mutated query/document")
        rows.append(row)
        if index % 30 == 0:
            print(f"  {index}: {name}", flush=True)
    return {"reverse_imports": reverse, "cpu": affinity, "rows": rows}


def summarize(runs):
    rows = []
    for index, first in enumerate(runs[0]["rows"]):
        row = {k: first[k] for k in ("name", "expected", "server", "status")}
        row["timings"] = {}
        for operation in first["timings"]:
            samples = {}
            for r in runs:
                for slot, values in r["rows"][index]["timings"][operation]["samples_us"].items():
                    samples.setdefault(slot, []).extend(values)
            base = samples["mgqpy"]
            row["timings"][operation] = {
                "median_us": {slot: statistics.median(v) for slot, v in samples.items()},
                "paired_ratio_to_mgqpy": {slot: statistics.median(b / a for a, b in zip(base, v))
                                          for slot, v in samples.items() if slot != "mgqpy"},
            }
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--libraries", nargs="+", default=DEFAULT)
    parser.add_argument("--ports", nargs="+", type=int, default=[27017])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cases", nargs="+", default=[])
    parser.add_argument("--operations", nargs="+", choices=OPERATIONS, default=list(OPERATIONS))
    parser.add_argument("--processes", type=int, default=2)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=.005)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--worker", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        config = json.loads(Path(args.worker[0]).read_text())
        Path(args.worker[2]).write_text(json.dumps(worker(config, bool(int(args.worker[1])))))
        return 0
    assert args.libraries[0] == "mgqpy", "mgqpy is the baseline and must come first"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    truth = server_truth(args.ports, args.cases)
    versions = truth.pop("__versions__")
    config = {"libraries": args.libraries, "cases": args.cases, "operations": args.operations,
              "processes": args.processes, "blocks": args.blocks, "seconds": args.seconds,
              "warmups": args.warmups, "cpu": args.cpu, "truth": truth}
    config_path = args.output.with_suffix(".config.json")
    config_path.write_text(json.dumps(config))
    runs = []
    for process in range(args.processes):
        print(f"process {process + 1}/{args.processes}", flush=True)
        part = args.output.with_suffix(".part.json")
        subprocess.run([sys.executable, __file__, "--worker", str(config_path), str(process % 2), str(part)],
                       check=True, env={**os.environ, "PYTHONHASHSEED": "0"})
        runs.append(json.loads(part.read_text()))
        part.unlink()
    config_path.unlink()
    data = {"schema": 1, "started_utc": started, "python": sys.version, "platform": platform.platform(),
            "hardware": run.hardware(), "timer": "time.process_time", "pythonhashseed": "0",
            "mongodb_versions": versions,
            "libraries": {n: {"version": adapters.version(n), "entry_point": adapters.LIBRARIES[n][1]()[2]}
                          for n in args.libraries},
            "config": {k: v for k, v in config.items() if k != "truth"},
            "harness_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (Path(__file__), HERE / "adapters.py", HERE.parent / "run.py",
                                         HERE.parent / "cases.py")},
            "runs": runs, "results": summarize(runs)}
    args.output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print("done", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
