#!/usr/bin/env python3
"""Time sift and mingo on benchmarks/cases.py in Node; separate from perf.py.

    python benchmarks/compare/perf_js.py --ports 27017 27018 --output results/perf-js.json

Same cases and eligibility rule as perf.py (real MongoDB and the library both
return the case's expected bool). Cases JavaScript cannot represent unchanged
are excluded. Timings are Node process CPU time; sift is the baseline and a
second independent sift module instance is the identical-source control.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import run  # noqa: E402
from cases import cases  # noqa: E402
from compat import JS, Unrepresentable, js_encode  # noqa: E402
from perf import OPERATIONS, server_truth  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ports", nargs="+", type=int, default=[27017])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=[])
    parser.add_argument("--operations", nargs="+", choices=OPERATIONS, default=list(OPERATIONS))
    parser.add_argument("--processes", type=int, default=2)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=.005)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--cpu", type=int)
    args = parser.parse_args()
    # Node runs with cwd js/, so pass it absolute paths.
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    truth = server_truth(args.ports, args.cases)
    versions = truth.pop("__versions__")
    exported, unrepresentable = [], {}
    for index, (name, query, document, expected) in cases(args.cases):
        try:
            encoded = json.dumps([js_encode(query), js_encode(document)], allow_nan=False)
        except Unrepresentable as error:
            unrepresentable[name] = str(error)
            continue
        exported.append({"index": index, "name": name, "expected": expected,
                         "server": truth[name], "encoded": encoded})
    config = {"cases": exported, "operations": args.operations, "blocks": args.blocks,
              "seconds": args.seconds, "warmups": args.warmups}
    config_path = args.output.with_suffix(".config.json")
    config_path.write_text(json.dumps(config))
    runs = []
    for process in range(args.processes):
        print(f"node process {process + 1}/{args.processes}", flush=True)
        part = args.output.with_suffix(".part.json")
        command = ["node", "--expose-gc", str(JS / "perf.mjs"), str(config_path), str(process % 2), str(part)]
        if args.cpu is not None:
            command = ["taskset", "-c", str(args.cpu)] + command
        subprocess.run(command, check=True, cwd=JS)
        runs.append(json.loads(part.read_text()))
        part.unlink()
    config_path.unlink()
    results = []
    for index, first in enumerate(runs[0]["rows"]):
        row = {k: first[k] for k in ("name", "expected", "server", "status")}
        row["timings"] = {}
        for operation in first["timings"]:
            samples = {}
            for r in runs:
                for slot, values in r["rows"][index]["timings"][operation]["samples_us"].items():
                    samples.setdefault(slot, []).extend(values)
            ratios = {}
            if "sift" in samples:
                ratios = {slot: statistics.median(b / a for a, b in zip(samples["sift"], v))
                          for slot, v in samples.items() if slot != "sift"}
            row["timings"][operation] = {
                "median_us": {slot: statistics.median(v) for slot, v in samples.items()},
                "paired_ratio_to_sift": ratios}
        results.append(row)
    package = lambda name: json.loads((JS / "node_modules" / name / "package.json").read_text())["version"]
    data = {"schema": 1, "started_utc": started, "node": subprocess.check_output(["node", "--version"], text=True).strip(),
            "platform": platform.platform(), "hardware": run.hardware(), "timer": "process.cpuUsage (user+system)",
            "mongodb_versions": versions, "cpu": args.cpu,
            "libraries": {"sift": package("sift"), "mingo": package("mingo")},
            "config": {k: v for k, v in config.items() if k != "cases"},
            "unrepresentable_cases": unrepresentable,
            "harness_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (Path(__file__), JS / "perf.mjs", HERE / "compat.py", HERE.parent / "cases.py")},
            "runs": runs, "results": results}
    args.output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print("done", args.output, len(exported), "cases exported,", len(unrepresentable), "unrepresentable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
