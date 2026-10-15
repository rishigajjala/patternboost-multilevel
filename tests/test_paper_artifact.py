from __future__ import annotations

import csv
import importlib.util
import json
import os
import shutil
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from multilevel import paper_artifact as paper


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence():
    data = ROOT / paper.ARTIFACT / "data"
    rows = [json.loads(line) for line in (data / "final_81_runtime.jsonl").read_text().splitlines()]
    seeds = json.loads((data / "final_81_seeds.json").read_text())["records"]
    with (data / "final_81_runs.csv").open(newline="") as handle:
        final = list(csv.DictReader(handle))
    return rows, seeds, final


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("artifact_reproduce", ROOT / "reproduce.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_published_matrix_has_recorded_seeds_and_three_historical_cohorts():
    rows = paper.load_paper_rows(ROOT)
    assert len(rows) == 81
    assert Counter(row["problem"] for row in rows) == {"misr": 27, "unit_square": 27, "guillotine": 27}
    assert Counter(row["git_commit"][:12] for row in rows) == paper.COHORT_COUNTS
    expected = {
        "misr": (5381899176938748427, 8, 32, 6, 7),
        "guillotine": (4475353812576049258, 8, 32, 6, 7),
        "unit_square": (2072069136256961140, 20, 32, 12, 10),
    }
    for problem, values in expected.items():
        selected = paper.select_rows(rows, problem=problem)
        assert len(selected) == 1
        row = selected[0]
        assert paper.config_id(row) == paper.BEST_CONFIGS[problem]
        assert tuple(row[key] for key in ("rng_seed", "n", "population", "elite", "train_every")) == values


@pytest.mark.parametrize("corruption,match", [
    ("rounded_seed", "rng_seed_decimal"), ("wrong_cohort_n", "n must"),
    ("duplicate", "Duplicate configuration"), ("missing", "exactly 81"),
    ("wrong_manifest_hash", "certificate_hash"),
])
def test_matrix_validation_rejects_broken_evidence(evidence, corruption, match):
    rows, seeds, final = deepcopy(evidence)
    if corruption == "rounded_seed":
        rows[0]["rng_seed"] += 1
    elif corruption == "wrong_cohort_n":
        row = next(row for row in rows if row["git_commit"].startswith("20750a588a5b"))
        row["n"] = 12
    elif corruption == "duplicate":
        rows[-1] = rows[0]
    elif corruption == "missing":
        rows.pop()
    else:
        seeds[0]["certificate_hash"] = "0" * 64
    with pytest.raises(ValueError, match=match):
        paper.validate_paper_rows(rows, seeds, final)


def test_overrides_change_saved_rows_without_mutating_historical_data():
    original = paper.load_paper_rows(ROOT)
    saved = deepcopy(original)
    rows = paper.select_rows(original, iterations=200, budget_seconds=60, checkpoint_every=20)
    assert len(rows) == 81
    assert all((row["iterations"], row["budget_seconds"], row["checkpoint_every"]) == (200, 60, 20) for row in rows)
    assert original == saved
    assert [row["rng_seed"] for row in rows] == [row["rng_seed"] for row in original]


def test_default_model_modes_are_preserved_and_overrides_are_explicit():
    original = paper.load_paper_rows(ROOT)
    saved = deepcopy(original)
    selected = paper.select_rows(original)
    assert selected == original
    assert Counter(row["model_kind"] for row in selected) == {"transformer": 77, "auto": 4}
    for kind in ("transformer", "ngram"):
        overridden = paper.select_rows(original, model_kind=kind)
        assert all(row["model_kind"] == kind for row in overridden)
    assert original == saved


def test_explicit_and_fresh_seeds_preserve_exact_integers(monkeypatch):
    original = paper.load_paper_rows(ROOT)
    explicit = 2**63 - 1
    assert paper.select_rows(original, problem="misr", seed=explicit)[0]["rng_seed"] == explicit
    values = iter(range(100, 181))
    monkeypatch.setattr(paper.secrets, "randbits", lambda bits: next(values))
    assert [row["rng_seed"] for row in paper.select_rows(original, fresh_seeds=True)] == list(range(100, 181))
    with pytest.raises(ValueError, match="requires one problem"):
        paper.select_rows(original, seed=1)
    with pytest.raises(ValueError, match="Expected exactly one"):
        paper.select_rows([], problem="unit_square")


@pytest.mark.parametrize("problem", tuple(paper.BEST_CONFIGS))
def test_selected_row_reaches_search_with_its_cohort_settings(tmp_path, monkeypatch, problem):
    # Exercise the actual CLI dispatch, replacing only the expensive search.
    from multilevel import cli

    row = paper.select_rows(paper.load_paper_rows(ROOT), problem=problem, iterations=2, budget_seconds=60)[0]
    matrix = tmp_path / "matrix.jsonl"
    matrix.write_text(json.dumps(row) + "\n")
    received = {}

    def fake_search(**kwargs):
        received.update(kwargs)
        return {"checked": True}

    monkeypatch.setattr(cli, "run_patternboost", fake_search)
    assert cli.main(["patternboost-cell", "--matrix", str(matrix), "--index", "0", "--out-root", str(tmp_path), "--iterations", "100", "--population", "99"]) == 0
    assert received["problem"] == problem
    assert received["seed"] == row["rng_seed"]
    assert received["population_size"] == row["population"]
    assert received["elite_size"] == row["elite"]
    assert received["train_every"] == row["train_every"]
    assert received["n"] == row["n"]
    assert received["iterations"] == 2
    assert received["budget_seconds"] == 60
    assert received["model_kind"] == "transformer"


def test_all_81_certificates_required_before_verification(tmp_path):
    assert len(paper.certificate_entries(ROOT)) == 81
    root = tmp_path / "artifact"
    data = root / paper.ARTIFACT / "data"
    data.mkdir(parents=True)
    for name in ("final_81_runtime.jsonl", "final_81_seeds.json", "final_81_runs.csv"):
        shutil.copy2(ROOT / paper.ARTIFACT / "data" / name, data / name)
    certs = root / paper.ARTIFACT / "run_artifacts"
    certs.mkdir()
    shutil.copy2(ROOT / paper.ARTIFACT / "run_artifacts/artifact_mapping.csv", certs / "artifact_mapping.csv")
    with pytest.raises(FileNotFoundError, match="Missing certificate"):
        paper.certificate_entries(root)


def _task(tmp_path: Path, index: int, exit_code: int = 0) -> paper.CellTask:
    return paper.CellTask(index, (sys.executable, "-c", f"print('worker {index}'); raise SystemExit({exit_code})"), str(tmp_path), os.environ.copy(), str(tmp_path / f"{index}.log"))


@pytest.mark.parametrize("parallel", [1, 2])
def test_workers_execute_and_propagate_nonzero_exit(tmp_path, parallel):
    success = paper.run_tasks([_task(tmp_path, 0), _task(tmp_path, 1)], parallel=parallel)
    assert [(r.index, r.returncode) for r in success] == [(0, 0), (1, 0)]
    assert "worker 1" in (tmp_path / "1.log").read_text()
    with pytest.raises(paper.BatchFailure) as caught:
        paper.run_tasks([_task(tmp_path, 2), _task(tmp_path, 3, 7)], parallel=parallel)
    assert [(r.index, r.returncode) for r in caught.value.results] == [(2, 0), (3, 7)]


def test_worker_start_failure_is_not_reported_as_success(tmp_path):
    task = paper.CellTask(0, ("/nonexistent/patternboost-python",), str(tmp_path), os.environ.copy(), str(tmp_path / "failure.log"))
    with pytest.raises(paper.BatchFailure) as caught:
        paper.run_tasks([task], parallel=2)
    assert caught.value.results[0].returncode == 125
    assert caught.value.results[0].error


def test_smoke_never_checks_torch_or_passes_an_invalid_model_flag(runner, tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(runner, "require_search_model", lambda *_: pytest.fail("smoke must not require torch"))
    monkeypatch.setattr(runner, "_run_checked", lambda command, env: commands.append(command))
    assert runner.main(["--mode", "smoke", "--out-root", str(tmp_path)]) == 0
    assert len(commands) == 1
    assert commands[0][2:4] == ("multilevel.cli", "smoke")
    assert "--model-kind" not in commands[0]


def test_dry_run_materializes_overrides_without_search_or_torch(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "require_search_model", lambda *_: pytest.fail("dry-run must not require torch"))
    monkeypatch.setattr(runner, "_execute", lambda *_: pytest.fail("dry-run must not search"))
    assert runner.main(["--mode", "full", "--paper-seeds", "--dry-run", "--iterations", "3", "--budget-seconds", "20", "--out-root", str(tmp_path)]) == 0
    root = next(tmp_path.iterdir())
    rows = [json.loads(line) for line in (root / "matrix.jsonl").read_text().splitlines()]
    assert len(rows) == 81
    assert all(row["iterations"] == 3 and row["budget_seconds"] == 20 for row in rows)
    assert json.loads((root / "run_manifest.json").read_text())["seed_mode"] == "recorded"


def test_matrix_mode_and_unique_outputs_do_not_overwrite(runner, tmp_path):
    args = ["--mode", "matrix", "--out-root", str(tmp_path)]
    assert runner.main(args) == 0
    assert runner.main(args) == 0
    assert len(list(tmp_path.glob("*/matrix.jsonl"))) == 2
    for matrix_file in tmp_path.glob("*/matrix.jsonl"):
        assert [json.loads(line) for line in matrix_file.read_text().splitlines()] == paper.load_paper_rows(ROOT)
    explicit = tmp_path / "named.jsonl"
    assert runner.main(args + ["--out", str(explicit)]) == 0
    previous = explicit.read_bytes()
    assert runner.main(args + ["--out", str(explicit)]) == 1
    assert explicit.read_bytes() == previous


def test_missing_torch_fails_search_instead_of_silently_falling_back(runner, tmp_path, monkeypatch):
    def no_torch(_name):
        raise ModuleNotFoundError("torch")

    monkeypatch.setattr(runner.importlib, "import_module", no_torch)
    assert runner.main(["--mode", "single", "--problem", "misr", "--out-root", str(tmp_path)]) == 1
    assert runner.main(["--mode", "full", "--out-root", str(tmp_path)]) == 1
    assert not list(tmp_path.iterdir())
    assert runner.main(["--mode", "single", "--model-kind", "ngram", "--dry-run", "--out-root", str(tmp_path)]) == 0
    manifest = json.loads(next(tmp_path.glob("*/run_manifest.json")).read_text())
    assert manifest["non_paper_sampler"] is True


def test_cli_returns_failure_and_records_failed_batch(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "require_search_model", lambda *_: None)

    def fail(_tasks, *, parallel):
        raise paper.BatchFailure([paper.CellResult(0, 9)])

    monkeypatch.setattr(runner, "run_tasks", fail)
    assert runner.main(["--mode", "single", "--out-root", str(tmp_path)]) == 1
    result = json.loads(next(tmp_path.glob("*/execution_results.json")).read_text())
    assert result["success"] is False
    assert result["cells"][0]["returncode"] == 9
