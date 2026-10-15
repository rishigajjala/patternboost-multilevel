from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from multilevel import components


def _load_analyzer():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_model_capacity.py"
    spec = importlib.util.spec_from_file_location("analyze_model_capacity", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("include_reference", [True, False])
def test_capacity_analysis_accepts_matrix_with_optional_reference(
    tmp_path, monkeypatch, include_reference
):
    analyzer = _load_analyzer()
    seeds = iter(range(18))
    monkeypatch.setattr(components, "fresh_rng_seed", lambda: next(seeds))
    rows = components.build_model_capacity_matrix(
        stage="model_capacity", budget_seconds=7200, git_commit="test_revision"
    )
    assert len(rows) == 18
    references = {row["run_id"]: row["reference_score"] for row in rows}
    if not include_reference:
        for row in rows:
            row.pop("reference_score")
            row.pop("reference_score_fraction")

    matrix = tmp_path / "matrix.jsonl"
    matrix.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    results = tmp_path / "results"
    # One completed comparison and eight missing pairs also exercise the normal
    # partial-results report without confusing a paper reference with a result.
    for row in rows[:2]:
        directory = results / row["experiment_arm"]
        directory.mkdir(parents=True)
        summary = {
            "run_id": row["run_id"],
            "best_exact_score": 1.25 if row["experiment_arm"] == "compact" else 1.5,
            "completed_iterations": 125,
            "elapsed_seconds": 7200,
            "stop_reason": "budget_exhausted",
        }
        (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    out_csv = tmp_path / "capacity.csv"
    out_md = tmp_path / "capacity.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_model_capacity.py",
            "--matrix", str(matrix),
            "--results-root", str(results),
            "--out-csv", str(out_csv),
            "--out-md", str(out_md),
        ],
    )
    assert analyzer.main() == 0

    with out_csv.open(newline="", encoding="utf-8") as handle:
        output = list(csv.DictReader(handle))
    assert len(output) == 18
    for row in output:
        if include_reference:
            assert float(row["reference_score"]) == references[row["run_id"]]
        else:
            assert row["reference_score"] == ""
    assert float(output[0]["best_exact_score"]) == 1.25
    assert float(output[1]["score_delta_vs_compact"]) == 0.25
    assert output[2]["best_exact_score"] == ""
    assert output[2]["stop_reason"] == "missing"
    assert "Complete comparisons: 1/9. Scaled better: 1; tied: 0; worse: 0; incomplete: 8." in out_md.read_text()
