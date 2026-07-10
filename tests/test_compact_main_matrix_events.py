from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


def _load_compactor():
    script = Path(__file__).resolve().parents[1] / "scripts" / "compact_main_matrix_events.py"
    spec = importlib.util.spec_from_file_location("compact_main_matrix_events", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _make_row(root: Path, problem: str, score: float) -> None:
    row_dir = root / "main" / problem / "representation" / "local_search" / "surrogate"
    row_dir.mkdir(parents=True)
    certificate = {
        "schema": f"{problem}_certificate_v1",
        "problem": problem,
        "score": score,
        "solver_status": "optimal",
        "certificate_hash": f"hash-{problem}",
    }
    if problem == "unit_square":
        certificate.update({"squares": [[0, 0]] * 8, "tau_int": 4, "tau_lp": 4 / score})
    else:
        certificate["rectangles"] = [[0, 1, 0, 1]] * 8
        if problem == "misr":
            certificate.update({"alpha_int": 4, "alpha_lp": 4 * score})
        else:
            certificate.update({"saved": round(8 * (1 - score)), "destroyed": round(8 * score)})
    _write_json(row_dir / "best.json", certificate)

    initial_score = score / 2
    events = [
        {
            "schema": "candidate_event_v1",
            "time": "2026-07-10T00:00:00+00:00",
            "problem": problem,
            "representation": "representation",
            "local_search": "local_search",
            "surrogate": "surrogate",
            "generation": 0,
            "source_type": "initial",
            "candidate_id": "initial",
            "exact_status": "optimal",
            "exact_score": initial_score,
            "best_exact_score": initial_score,
        },
        {
            "schema": "model_event_v1",
            "time": "2026-07-10T00:00:10+00:00",
            "generation": 10,
            "model_kind": "transformer",
            "num_training_texts": 8,
            "num_requested_samples": 16,
        },
        {
            "schema": "candidate_event_v1",
            "time": "2026-07-10T00:00:20+00:00",
            "problem": problem,
            "representation": "representation",
            "local_search": "local_search",
            "surrogate": "surrogate",
            "generation": 10,
            "source_type": "model_sample",
            "candidate_id": "best",
            "exact_status": "optimal",
            "exact_score": score,
            "best_exact_score": score,
        },
    ]
    (row_dir / "events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    _write_json(
        row_dir / "checkpoint.json",
        {
            "schema": "patternboost_checkpoint_v1",
            "run_id": f"{problem}/representation/local_search/surrogate/budget20/gitabc123",
            "next_generation": 20,
            "best_exact_score": score,
            "best_certificate_path": "best.json",
            "num_model_train_calls": 1,
        },
    )
    _write_json(
        row_dir / "summary.json",
        {
            "schema": "run_summary_v1",
            "run_id": f"{problem}/representation/local_search/surrogate/budget20/gitabc123",
            "problem": problem,
            "representation": "representation",
            "local_search": "local_search",
            "surrogate": "surrogate",
            "start_time": "2026-07-10T00:00:00+00:00",
            "completed_iterations": 20,
            "stop_reason": "budget_exhausted",
            "return_code": 0,
            "elapsed_seconds": 20.0,
            "best_exact_score": score,
            "time_to_best": 20.0,
            "best_certificate_path": "best.json",
            "best_certificate_hash": f"hash-{problem}",
            "num_exact_calls": 2,
            "num_model_train_calls": 1,
            "num_model_samples": 16,
            "num_model_samples_valid": 8,
            "model_hparams": {"epochs": 3},
        },
    )


def test_compact_run_preserves_improvements_and_epochs(tmp_path: Path) -> None:
    module = _load_compactor()
    root = tmp_path / "main_results"
    _make_row(root, "misr", 1.5)
    _make_row(root, "unit_square", 1.5)
    _make_row(root, "guillotine", 0.25)
    out = tmp_path / "analysis"

    manifest = module.compact_run(
        root,
        out,
        expected_rows=3,
        default_model_epochs=3,
        strict=True,
    )

    assert manifest["rows_found"] == 3
    assert manifest["summary_count"] == 3
    assert manifest["certificate_count"] == 3
    assert manifest["issues"] == []

    with (out / "row_metrics.csv").open(newline="", encoding="utf-8") as handle:
        metrics = list(csv.DictReader(handle))
    assert {row["problem"] for row in metrics} == {"misr", "unit_square", "guillotine"}
    assert all(row["model_train_calls"] == "1" for row in metrics)
    assert all(row["total_model_epochs"] == "3" for row in metrics)
    assert all(row["improvement_count"] == "2" for row in metrics)
    assert all(row["source_of_best"] == "model_sample" for row in metrics)

    with (out / "score_improvements.csv").open(newline="", encoding="utf-8") as handle:
        improvements = list(csv.DictReader(handle))
    assert len(improvements) == 6
    assert {row["cumulative_model_epochs"] for row in improvements} == {"0", "3"}


def test_normalized_curve_uses_first_audited_score_as_baseline() -> None:
    module = _load_compactor()
    point = module.Improvement(
        generation=20,
        elapsed_seconds=10.0,
        model_train_calls=2,
        cumulative_model_epochs=6,
        best_score=0.25,
        exact_score=0.25,
        source_type="local_mutation",
        candidate_id="candidate",
    )

    assert module._step_score([point], axis="model_epoch", target=0.0) == 0.25
