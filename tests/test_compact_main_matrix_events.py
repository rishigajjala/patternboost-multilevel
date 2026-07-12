from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


CERTIFICATE_SCHEMAS = {
    "misr": "misr_certificate_v1",
    "unit_square": "unit_square_stab_certificate_v1",
    "guillotine": "guillotine_certificate_v1",
}


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


def _certificate_hash(certificate: dict) -> str:
    payload = dict(certificate)
    payload.pop("certificate_hash", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _make_row(
    root: Path,
    problem: str,
    score: float,
    *,
    representation: str = "representation",
    local_search: str = "local_search",
    surrogate: str = "surrogate",
) -> Path:
    row_dir = root / "main" / problem / representation / local_search / surrogate
    row_dir.mkdir(parents=True)
    certificate = {
        "schema": CERTIFICATE_SCHEMAS[problem],
        "problem": problem,
        "score": score,
        "solver_status": "optimal",
    }
    if problem == "unit_square":
        certificate.update({"squares": [[0, 0]] * 8, "tau_int": 4, "tau_lp": 4 / score})
    else:
        certificate["rectangles"] = [[0, 1, 0, 1]] * 8
        if problem == "misr":
            certificate.update({"alpha_int": 4, "alpha_lp": 4 * score})
        else:
            certificate.update({"saved": round(8 * (1 - score)), "destroyed": round(8 * score)})
    certificate["certificate_hash"] = _certificate_hash(certificate)
    _write_json(row_dir / "best.json", certificate)

    initial_score = score / 2
    events = [
        {
            "schema": "candidate_event_v1",
            "time": "2026-07-10T00:00:00+00:00",
            "problem": problem,
            "representation": representation,
            "local_search": local_search,
            "surrogate": surrogate,
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
            "representation": representation,
            "local_search": local_search,
            "surrogate": surrogate,
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
            "run_id": f"{problem}/{representation}/{local_search}/{surrogate}/budget20/gitabc123",
            "next_generation": 20,
            "best_exact_score": score,
            "best_certificate_path": "best.json",
            "best_certificate_hash": certificate["certificate_hash"],
            "num_model_train_calls": 1,
        },
    )
    _write_json(
        row_dir / "summary.json",
        {
            "schema": "run_summary_v1",
            "run_id": f"{problem}/{representation}/{local_search}/{surrogate}/budget20/gitabc123",
            "problem": problem,
            "representation": representation,
            "local_search": local_search,
            "surrogate": surrogate,
            "start_time": "2026-07-10T00:00:00+00:00",
            "completed_iterations": 20,
            "stop_reason": "budget_exhausted",
            "return_code": 0,
            "elapsed_seconds": 20.0,
            "best_exact_score": score,
            "time_to_best": 20.0,
            "best_certificate_path": "best.json",
            "best_certificate_hash": certificate["certificate_hash"],
            "num_exact_calls": 2,
            "num_model_train_calls": 1,
            "num_model_samples": 16,
            "num_model_samples_valid": 8,
            "model_hparams": {"epochs": 3},
        },
    )
    return row_dir


def _sync_state_hashes(row_dir: Path, certificate_hash: str) -> None:
    for filename in ("summary.json", "checkpoint.json"):
        path = row_dir / filename
        state = json.loads(path.read_text(encoding="utf-8"))
        state["best_certificate_hash"] = certificate_hash
        _write_json(path, state)


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


def test_strict_validation_rejects_malformed_certificate_json(tmp_path: Path) -> None:
    module = _load_compactor()
    root = tmp_path / "main_results"
    row_dir = _make_row(root, "misr", 1.5)
    (row_dir / "best.json").write_text('{"schema":', encoding="utf-8")
    out = tmp_path / "analysis"

    with pytest.raises(SystemExit, match="malformed certificate JSON"):
        module.compact_run(
            root,
            out,
            expected_rows=1,
            default_model_epochs=3,
            strict=True,
        )

    manifest = json.loads((out / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert manifest["resolved_certificate_count"] == 1
    assert manifest["certificate_count"] == 0


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("schema", "misr_certificate_v0", "certificate schema"),
        ("certificate_hash", "not-the-content-hash", "certificate hash"),
        ("score", 1.75, "certificate score"),
    ],
)
def test_strict_validation_rejects_inconsistent_certificate_fields(
    tmp_path: Path,
    field: str,
    value,
    expected_error: str,
) -> None:
    module = _load_compactor()
    root = tmp_path / "main_results"
    row_dir = _make_row(root, "misr", 1.5)
    certificate_path = row_dir / "best.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate[field] = value
    if field != "certificate_hash":
        certificate["certificate_hash"] = _certificate_hash(certificate)
        _sync_state_hashes(row_dir, certificate["certificate_hash"])
    _write_json(certificate_path, certificate)

    with pytest.raises(SystemExit, match=expected_error):
        module.compact_run(
            root,
            tmp_path / "analysis",
            expected_rows=1,
            default_model_epochs=3,
            strict=True,
        )


def test_partial_batch_accepts_uneven_explicit_expectations(tmp_path: Path) -> None:
    module = _load_compactor()
    root = tmp_path / "main_results"
    _make_row(root, "misr", 1.5, representation="misr_a")
    _make_row(root, "misr", 1.25, representation="misr_b")
    _make_row(root, "unit_square", 1.5, representation="unit_a")
    expected_configs = {
        "misr/misr_a/local_search/surrogate",
        "misr/misr_b/local_search/surrogate",
        "unit_square/unit_a/local_search/surrogate",
    }

    manifest = module.compact_run(
        root,
        tmp_path / "analysis",
        expected_rows=3,
        expected_problem_counts={"misr": 2, "unit_square": 1},
        expected_configs=expected_configs,
        default_model_epochs=3,
        strict=True,
    )

    assert manifest["issues"] == []
    assert manifest["expected_problem_counts"] == {
        "guillotine": 0,
        "misr": 2,
        "unit_square": 1,
    }
    assert manifest["expected_config_count"] == 3


def test_partial_batch_without_distribution_does_not_assume_equal_counts(
    tmp_path: Path,
) -> None:
    module = _load_compactor()
    root = tmp_path / "main_results"
    _make_row(root, "misr", 1.5, representation="misr_a")
    _make_row(root, "misr", 1.25, representation="misr_b")
    _make_row(root, "unit_square", 1.5, representation="unit_a")

    manifest = module.compact_run(
        root,
        tmp_path / "analysis",
        expected_rows=3,
        default_model_epochs=3,
        strict=True,
    )

    assert manifest["issues"] == []
    assert manifest["expected_problem_counts"] == {}


def test_default_81_row_contract_still_requires_27_rows_per_problem() -> None:
    module = _load_compactor()
    rows = [
        SimpleNamespace(problem=problem, config_id=f"{problem}/rep_{index}/local/model")
        for problem, count in (("misr", 28), ("unit_square", 26), ("guillotine", 27))
        for index in range(count)
    ]

    issues, expected_counts, expected_configs = module._batch_expectation_issues(
        rows,
        expected_rows=81,
        expected_problem_counts=None,
        expected_configs=None,
    )

    assert expected_counts == {"misr": 27, "unit_square": 27, "guillotine": 27}
    assert expected_configs is None
    assert "misr: expected 27 rows, found 28" in issues
    assert "unit_square: expected 27 rows, found 26" in issues


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
