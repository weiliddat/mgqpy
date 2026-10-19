"""Opt-in harness contract checks, not performance thresholds or CI benchmarks."""

import csv
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

import pytest


@pytest.fixture
def repository(tmp_path):
    benchmarks = tmp_path / "benchmarks"
    benchmarks.mkdir()
    for name in ("run.py", "cases.py"):
        shutil.copyfile(Path(__file__).with_name(name), benchmarks / name)
    source = tmp_path / "src/mgqpy/__init__.py"
    source.parent.mkdir(parents=True)

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Benchmark test")
    git("config", "user.email", "benchmark@example.invalid")
    revisions = []
    for phase in ("ok", "construct", "validate", "match", "wrong"):
        source.write_text(f'''
PHASE = {phase!r}
class Query:
    def __init__(self, query):
        if PHASE == "construct":
            raise ValueError("constructor failed")
        self.query = query
    def validate(self):
        if PHASE == "validate":
            raise ValueError("validator failed")
    def test(self, document):
        if PHASE == "match":
            raise LookupError("evaluation failed")
        if PHASE == "wrong":
            return False
        return document.get("x") == self.query["x"]
''')
        git("add", "src")
        git("commit", "-qm", phase)
        revisions.append(git("rev-parse", "HEAD"))
    return tmp_path, revisions


def test_cli_isolates_refs_flags_phases_and_pools_paired_samples(repository):
    root, refs = repository
    output = root / "result.json"
    subprocess.run([sys.executable, "benchmarks/run.py", *refs, refs[0],
                    "--cases", "flat", "--blocks", "2", "--seconds", ".0001",
                    "--warmups", "1", "--output", str(output)], cwd=root, check=True)
    data = json.loads(output.read_text())
    row = data["results"][0]
    assert data["refs"]["0"]["commit"] == refs[0]
    assert row["difference"]
    assert [row["status"][str(i)]["eligible"] for i in range(6)] == [True, False, False, False, False, True]
    assert row["status"]["1"]["outcome"] == {
        "phase": "construct", "type": "ValueError", "message": "constructor failed"}
    assert row["status"]["2"]["validation"]["phase"] == "validate"
    assert row["status"]["3"]["outcome"]["type"] == "LookupError"
    assert row["status"]["4"]["outcome"]["value"] == "False"
    for operation in ("match", "construct", "single-use"):
        pairs = []
        for run in data["runs"]:
            samples = run["rows"][0]["timings"][operation]["samples_us"]
            assert "1" not in samples  # rejected construction is never timed
            pairs.extend(b / a for a, b in zip(samples["0"], samples["5"]))
        assert len(pairs) == 4
        assert row["timings"][operation]["paired_ratio"]["5"] == statistics.median(pairs)
        assert "2" not in row["timings"][operation]["paired_ratio"]
    with output.with_suffix(".csv").open() as stream:
        exported = list(csv.DictReader(stream))
    assert len(exported) == 18  # three operations × six requested refs
    assert exported[1]["median_us"] == ""


def test_cli_checks_without_timing_and_requires_acknowledging_last_ref_difference(repository):
    root, refs = repository
    command = [sys.executable, "benchmarks/run.py", refs[0], refs[-1],
               "--cases", "flat", "--check", "--output", str(root / "check.json")]
    assert subprocess.run(command, cwd=root).returncode == 1
    data = json.loads((root / "check.json").read_text())
    assert data["results"][0]["timings"] == {}
    assert subprocess.run(command + ["--allow-differences"], cwd=root).returncode == 0


@pytest.mark.parametrize("reuse_limit", [1, 10])
def test_cli_rejects_a_reused_predicate_that_stops_matching(repository, reuse_limit):
    root, refs = repository
    (root / "src/mgqpy/__init__.py").write_text(f'''
class Query:
    def __init__(self, query):
        self.calls = 0
    def test(self, document):
        self.calls += 1
        return self.calls <= {reuse_limit}
''')
    subprocess.run(["git", "add", "src"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "stateful predicate"], cwd=root, check=True)
    output = root / "result.json"
    result = subprocess.run([
        sys.executable, "benchmarks/run.py", refs[0], "HEAD", "--cases", "flat",
        "--operations", "match", "--warmups", "1", "--blocks", "1",
        "--seconds", ".0001", "--output", str(output),
    ], cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert not output.exists()  # Never publish a ratio for the changed answer.


@pytest.mark.parametrize("suffix", [".csv", ".CSV"])
def test_cli_rejects_colliding_output_paths_before_running(repository, suffix):
    root, refs = repository
    output = root / ("result" + suffix)
    output.write_text("keep existing output")
    result = subprocess.run([
        sys.executable, "benchmarks/run.py", refs[0], refs[0], "--cases", "flat",
        "--operations", "match", "--warmups", "1", "--blocks", "1",
        "--seconds", ".0001", "--output", str(output),
    ], cwd=root, capture_output=True, text=True)
    assert result.returncode == 2
    assert "--output" in result.stderr and ".csv" in result.stderr
    assert output.read_text() == "keep existing output"


def test_cli_keeps_deferred_imports_and_their_cache_local_to_each_ref(repository):
    root, _ = repository
    refs = []
    for value in (1000, 1):
        (root / "src/mgqpy/helper.py").write_text(f"VALUE = {value}\nTOKEN = object()\n")
        (root / "src/mgqpy/__init__.py").write_text(f'''
VERSION = {value}
class Query:
    def __init__(self, query):
        from mgqpy.helper import VALUE
        assert VALUE == VERSION
        self.query = query
        self.token = None
    def validate(self):
        from mgqpy.helper import VALUE
        assert VALUE == VERSION
    def test(self, document):
        from mgqpy.helper import TOKEN, VALUE
        if self.token is None:
            self.token = TOKEN
        return (VALUE == VERSION and TOKEN is self.token
                and document.get("x") == self.query["x"])
''')
        subprocess.run(["git", "add", "src"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "deferred imports"], cwd=root, check=True)
        refs.append(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip())
    output = root / "result.json"
    subprocess.run([
        sys.executable, "benchmarks/run.py", *refs, "--cases", "flat", "--warmups", "1",
        "--blocks", "2", "--seconds", ".0001", "--output", str(output),
    ], cwd=root, check=True)
    data = json.loads(output.read_text())
    assert all(status["eligible"] for run in data["runs"]
               for status in run["rows"][0]["status"].values())
    for operation in ("match", "construct", "single-use"):
        assert "1" in data["results"][0]["timings"][operation]["paired_ratio"]


@pytest.mark.parametrize("case,mutation", [
    ("large-in", 'self.query["x"]["$in"].append(-1)'),
    ("numeric-last", 'document["x"].sort(reverse=True)'),
    ("ordered-document", 'document["x"]["a"] = document["x"].pop("a")'),
])
def test_cli_rejects_input_mutation_even_when_the_answer_is_unchanged(repository, case, mutation):
    root, _ = repository
    refs = []
    for mutates in (False, True):
        (root / "src/mgqpy/__init__.py").write_text(f'''
class Query:
    def __init__(self, query):
        self.query = query
        self.calls = 0
    def test(self, document):
        self.calls += 1
        if self.calls == 2 and {mutates}:
            {mutation}
        return True
''')
        subprocess.run(["git", "add", "src"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "input mutation"], cwd=root, check=True)
        refs.append(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip())
    output = root / "result.json"
    result = subprocess.run([
        sys.executable, "benchmarks/run.py", *refs, "--cases", case, "--operations", "match",
        "--warmups", "1", "--blocks", "1", "--seconds", ".0001", "--output", str(output),
    ], cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert not output.exists()
