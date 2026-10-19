#!/usr/bin/env python3
"""Compare git refs without installing mgqpy. Standard library only; see README.md."""

import argparse
from contextlib import contextmanager
from copy import deepcopy
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import pickle
import platform
import random
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import timeit

from cases import cases


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OPERATIONS = ("match", "construct", "single-use")


@contextmanager
def activate(package):
    """Swap this ref's imports outside timing; retain modules imported lazily."""
    previous = {}
    for name in list(sys.modules):
        if name == "mgqpy" or name.startswith("mgqpy."):
            previous[name] = sys.modules.pop(name)
    sys.modules.update(package)
    try:
        yield
    finally:
        package.clear()
        for name in list(sys.modules):
            if name == "mgqpy" or name.startswith("mgqpy."):
                package[name] = sys.modules.pop(name)
        sys.modules.update(previous)


def load(root):
    """Retain independent module globals, including old circular package imports."""
    source = Path(root) / "src"
    package = {}
    with activate(package):
        sys.path.insert(0, str(source))
        try:
            module = importlib.import_module("mgqpy")
            for name, child in list(sys.modules.items()):
                if name == "mgqpy" or name.startswith("mgqpy."):
                    if child.__file__ is not None:
                        assert Path(child.__file__).resolve().is_relative_to(source)
                    else:
                        assert all(Path(p).is_relative_to(source) for p in child.__path__)
                    if hasattr(child, "mgqpy"):
                        assert child.mgqpy is module
            assert Path(module.Query.__init__.__globals__["__file__"]).is_relative_to(source)
        finally:
            sys.path.pop(0)
    return package


def error_outcome(phase, error):
    return {"phase": phase, "type": type(error).__name__, "message": str(error)}


def check(module, query, document, expected):
    try:
        predicate = module.Query(query)
    except Exception as error:
        return {"outcome": error_outcome("construct", error), "eligible": False}, None
    # 0.9 stores an unchecked reference. Record its optional validation separately,
    # never time it or quietly count a rejected query as equivalent work.
    validation = "ok"
    if hasattr(predicate, "validate"):
        try:
            predicate.validate()
        except Exception as error:
            validation = error_outcome("validate", error)
    try:
        actual = predicate.test(document)
        outcome = {"phase": "match", "type": type(actual).__name__, "value": repr(actual)}
        correct = type(actual) is bool and actual is expected
    except Exception as error:
        outcome = error_outcome("match", error)
        correct = False
    return {"outcome": outcome, "validation": validation,
            "eligible": correct and validation == "ok"}, predicate


def measure(functions, seed, config, expected, packages):
    timers = {name: timeit.Timer(fn, timer=time.process_time) for name, fn in functions.items()}
    for name, fn in functions.items():
        with activate(packages[name]):
            for _ in range(config["warmups"]):
                fn()
            if expected is not None:
                assert fn() is expected, (name, "incorrect answer after warmup")
    calibration = 0
    for name, timer in timers.items():
        with activate(packages[name]):
            calibration = max(calibration, timer.timeit(100) / 100)
    loops = max(20, min(100_000, int(config["seconds"] / max(calibration, 1e-9))))
    samples = {name: [] for name in timers}
    rng = random.Random(seed)
    for _ in range(config["blocks"]):
        order = list(timers)
        rng.shuffle(order)
        for name in order:
            with activate(packages[name]):
                # timeit disables GC only while timing. Destruction is included.
                samples[name].append(timers[name].timeit(loops) * 1e6 / loops)
        gc.collect()
    if expected is not None:
        for name, fn in functions.items():
            with activate(packages[name]):
                assert fn() is expected, (name, "incorrect answer after timing")
    return {"loops": loops, "samples_us": samples}


def worker(config, reverse):
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        allowed = os.sched_getaffinity(0)
        affinity = min(allowed) if config["cpu"] is None else config["cpu"]
        os.sched_setaffinity(0, {affinity})
    slots = list(config["sources"])
    order = list(reversed(slots)) if reverse else slots
    packages = {name: load(config["sources"][name]) for name in order}
    assert len({id(package["mgqpy"].Query) for package in packages.values()}) == len(packages)
    rows = []
    for index, (name, query, document, expected) in cases(config["cases"]):
        # Serialization preserves dict order and handles NaNs without equality.
        pristine = pickle.dumps((query, document))
        inputs = {slot: deepcopy((query, document)) for slot in slots}
        statuses, predicates = {}, {}
        for slot in slots:
            with activate(packages[slot]):
                statuses[slot], predicates[slot] = check(packages[slot]["mgqpy"], *inputs[slot], expected)
        row = {"name": name, "expected": expected, "status": statuses, "timings": {}}
        if not config["check"]:
            for operation in config["operations"]:
                functions = {}
                for slot in slots:
                    cls, predicate = packages[slot]["mgqpy"].Query, predicates[slot]
                    q, d = inputs[slot]
                    if operation == "construct" and predicate is not None:
                        functions[slot] = lambda cls=cls, q=q: cls(q)
                    elif statuses[slot]["eligible"]:
                        if operation == "match":
                            functions[slot] = lambda p=predicate, d=d: p.test(d)
                        else:
                            functions[slot] = lambda cls=cls, q=q, d=d: cls(q).test(d)
                if functions:
                    seed = 4361 + index + 1000 * OPERATIONS.index(operation)
                    row["timings"][operation] = measure(
                        functions, seed, config, None if operation == "construct" else expected, packages)
            # A warm cache or a timed operation must not change the answer.
            for slot in slots:
                with activate(packages[slot]):
                    after, _ = check(packages[slot]["mgqpy"], *inputs[slot], expected)
                assert after == statuses[slot], (name, slot, statuses[slot], after)
        for slot in slots:
            assert pickle.dumps(inputs[slot]) == pristine, (name, slot, "mutated query/document")
        rows.append(row)
        if index % 30 == 0:
            print(f"  {index}: {name}", flush=True)
    return {"reverse_imports": reverse, "cpu": affinity, "rows": rows}


def summarize(runs, refs):
    """Pool every paired block; never select the best process or average cases."""
    rows = []
    for index, first in enumerate(runs[0]["rows"]):
        row = {"name": first["name"], "expected": first["expected"],
               "status": first["status"], "timings": {}}
        for run in runs:
            assert run["rows"][index]["name"] == row["name"]
            assert run["rows"][index]["status"] == row["status"]
        outcomes = [(s["outcome"], s.get("validation", "ok")) for s in row["status"].values()]
        row["difference"] = any(o != outcomes[0] for o in outcomes) or any(
            not s["eligible"] for s in row["status"].values())
        for operation in first["timings"]:
            samples = {slot: [] for slot in first["timings"][operation]["samples_us"]}
            for run in runs:
                for slot, values in run["rows"][index]["timings"][operation]["samples_us"].items():
                    samples[slot].extend(values)
            ratios = {}
            for slot in list(refs)[1:] + ["control"]:
                base = list(refs)[-1] if slot == "control" else list(refs)[0]
                if (slot in samples and base in samples
                        and row["status"][slot]["eligible"] and row["status"][base]["eligible"]):
                    ratios[slot] = statistics.median(b / a for a, b in zip(samples[base], samples[slot]))
            row["timings"][operation] = {
                "median_us": {slot: statistics.median(v) for slot, v in samples.items()},
                "paired_ratio": ratios,
            }
        rows.append(row)
    return rows


def write_csv(path, data):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case", "operation", "variant", "median_us", "ratio_to_first",
                         "identical_source_ratio", "eligible", "status"])
        for row in data["results"]:
            for operation in data["config"]["operations"]:
                timing = row["timings"].get(operation, {})
                for slot in data["refs"]:
                    writer.writerow([row["name"], operation, data["refs"][slot]["label"],
                                     timing.get("median_us", {}).get(slot, ""),
                                     timing.get("paired_ratio", {}).get(slot, ""),
                                     timing.get("paired_ratio", {}).get("control", ""),
                                     row["status"][slot]["eligible"],
                                     json.dumps(row["status"][slot], sort_keys=True)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", nargs="*", help="two or more git refs, optionally LABEL=REF; first is baseline")
    parser.add_argument("--output", type=Path, help="JSON result (also writes CSV beside it)")
    parser.add_argument("--cases", nargs="+", default=[], help="case-name globs (quote '*')")
    parser.add_argument("--operations", nargs="+", choices=OPERATIONS, default=list(OPERATIONS))
    parser.add_argument("--processes", type=int, default=2, help="even count; alternate import order")
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=.005, help="target process CPU seconds per block")
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--cpu", type=int, help="Linux logical CPU; default first available")
    parser.add_argument("--check", action="store_true", help="check outcomes without timing")
    parser.add_argument("--allow-differences", action="store_true", help="also allow unexpected last-ref outcomes")
    parser.add_argument("--list", action="store_true", help="list selected cases without loading refs")
    args = parser.parse_args()
    selected = cases(args.cases)
    if not selected:
        parser.error("no cases selected")
    if args.list:
        for _, (name, _, _, expected) in selected:
            print(name, expected)
        return 0
    if len(args.refs) < 2 or args.output is None:
        parser.error("provide at least two refs and --output")
    if args.output.suffix.lower() == ".csv":
        parser.error("--output must not end in .csv; JSON and CSV paths would collide")
    if (args.processes < 2 or args.processes % 2 or args.blocks < 1 or args.warmups < 0
            or not math.isfinite(args.seconds) or args.seconds <= 0):
        parser.error("use an even process count >= 2, blocks >= 1, warmups >= 0 and seconds > 0")
    if args.cpu is not None and not hasattr(os, "sched_getaffinity"):
        parser.error("--cpu requires Linux CPU affinity")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    config = {key: value for key, value in vars(args).items() if key not in ("refs", "output", "list")}
    refs = {}
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="mgqpy-benchmark-") as temporary:
        temporary = Path(temporary)
        sources = {}
        for index, spec in enumerate(args.refs):
            label, ref = spec.split("=", 1) if "=" in spec else (spec, spec)
            sha = subprocess.check_output(["git", "rev-parse", "--verify", ref + "^{commit}"],
                                          cwd=ROOT, text=True).strip()
            slot = str(index)
            refs[slot] = {"label": label, "ref": ref, "commit": sha}
            archive = temporary / "source.tar"
            subprocess.run(["git", "archive", "--format=tar", "--output", str(archive), sha, "src"],
                           cwd=ROOT, check=True)
            source = temporary / slot
            source.mkdir()
            with tarfile.open(archive) as tar:
                # Reject archive links/traversal; only package source is needed.
                for member in tar.getmembers():
                    if (not (member.isfile() or member.isdir()) or Path(member.name).is_absolute()
                            or ".." in Path(member.name).parts):
                        raise ValueError(f"unsupported archive entry: {member.name}")
                if sys.version_info >= (3, 12):
                    tar.extractall(source, filter="data")
                else:
                    tar.extractall(source)
            sources[slot] = str(source)
        # An extra, independent import of the last ref measures same-source noise
        # alongside every workload, rather than applying a correction factor.
        sources["control"] = sources[str(len(refs) - 1)]
        config["sources"] = sources
        config_path = temporary / "config.json"
        config_path.write_text(json.dumps(config))
        runs = []
        for process in range(args.processes):
            print(f"Python {platform.python_version()}, process {process + 1}/{args.processes}", flush=True)
            result_path = temporary / "worker.json"
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(config_path),
                            str(process % 2), str(result_path)], cwd=ROOT, check=True,
                           env={**os.environ, "PYTHONHASHSEED": "0"})
            runs.append(json.loads(result_path.read_text()))
        del config["sources"]
    data = {"schema": 1, "started_utc": started, "python": sys.version,
            "platform": platform.platform(), "machine": platform.machine(),
            "timer": "time.process_time", "pythonhashseed": "0", "refs": refs, "config": config,
            "harness_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (Path(__file__), HERE / "cases.py")},
            "runs": runs, "results": summarize(runs, refs)}
    args.output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    write_csv(args.output.with_suffix(".csv"), data)
    differences = [row["name"] for row in data["results"] if row["difference"]]
    last = str(len(refs) - 1)
    unexpected = [row["name"] for row in data["results"] if not row["status"][last]["eligible"]]
    print(f"{len(selected)} cases; {len(differences)} differing/unsupported; "
          f"{len(unexpected)} unexpected last-ref outcomes. {args.output}")
    for operation in args.operations:
        controls = [row["timings"][operation]["paired_ratio"]["control"] for row in data["results"]
                    if "control" in row["timings"].get(operation, {}).get("paired_ratio", {})]
        if controls:
            print(f"  {operation}: identical-source ratios {min(controls):.3f}–{max(controls):.3f}")
    if differences:
        print("  Flagged cases: " + ", ".join(differences))
    return int(bool(unexpected) and not args.allow_differences)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        config = json.loads(Path(sys.argv[2]).read_text())
        Path(sys.argv[4]).write_text(json.dumps(worker(config, bool(int(sys.argv[3])))))
    else:
        sys.exit(main())
