from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_builder():
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_replacement_81_dataset.py"
    spec = importlib.util.spec_from_file_location("build_replacement_81_dataset", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_metrics(module) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for problem, cells in module.EXPECTED_CELLS.items():
        for representation, local_search, surrogate in sorted(cells):
            rows.append(
                {
                    "config_id": "/".join((problem, representation, local_search, surrogate)),
                    "problem": problem,
                    "representation": representation,
                    "local_search": local_search,
                    "surrogate": surrogate,
                }
            )
    for index, row in enumerate(rows):
        row["source_cohort"] = (
            "retained_24h_20260709" if index < 36 else "replacement_24h_20260711"
        )
    return rows


def test_validate_metrics_rejects_wrong_cartesian_cell_with_valid_counts() -> None:
    module = _load_builder()
    rows = _valid_metrics(module)
    module._validate_metrics(rows)

    adversarial = [dict(row) for row in rows]
    adversarial[0]["representation"] = "unexpected_representation"
    adversarial[0]["config_id"] = "/".join(
        (
            adversarial[0]["problem"],
            adversarial[0]["representation"],
            adversarial[0]["local_search"],
            adversarial[0]["surrogate"],
        )
    )

    try:
        module._validate_metrics(adversarial)
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("invalid Cartesian coverage was accepted")

    assert "missing=" in message
    assert "unexpected=" in message
    assert "unexpected_representation" in message


def test_fraction_only_emits_strictly_matching_rationals() -> None:
    module = _load_builder()

    assert module._fraction(1.5) == "3/2"
    assert module._fraction(20 / 13) == "20/13"
    assert module._fraction(1.4643545279383436) == ""
    assert module._fraction("not-a-number") == ""


def test_zero_total_epochs_leave_final_fraction_undefined() -> None:
    module = _load_builder()
    problem = module.PROBLEMS[0]
    representation, local_search, surrogate = sorted(module.EXPECTED_CELLS[problem])[0]
    metric = {
        "config_id": "/".join((problem, representation, local_search, surrogate)),
        "problem": problem,
        "representation": representation,
        "local_search": local_search,
        "surrogate": surrogate,
        "source_cohort": "replacement_24h_20260711",
        "source_run_group": "delta_45_matrix",
        "initial_best_score": "1.5",
        "best_score": "1.5",
        "completed_iterations": "10",
        "elapsed_seconds": "20",
        "model_train_calls": "0",
        "total_model_epochs": "0",
        "certificate_hash": "certificate-hash",
    }

    history = module._epoch_history([metric], [])
    final = history[-1]

    assert final["point_kind"] == "final_endpoint"
    assert final["cumulative_model_epochs"] == "0"
    assert final["model_epoch_fraction"] == ""

    metric["total_model_epochs"] = "3"
    assert module._epoch_history([metric], [])[-1]["model_epoch_fraction"] == 1
