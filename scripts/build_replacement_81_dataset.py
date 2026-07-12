#!/usr/bin/env python3
"""Merge the retained 36 cells and replacement 45 cells into final datasets."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from fractions import Fraction
from importlib import import_module
from itertools import product
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

components_module = import_module("multilevel.components")
REPLACEMENT_COMPONENTS = components_module.REPLACEMENT_COMPONENTS
REPLACEMENT_REMOVALS = components_module.REPLACEMENT_REMOVALS


PROBLEMS = tuple(REPLACEMENT_COMPONENTS)
REMOVED = {
    problem: (values["representation"], values["local_search"])
    for problem, values in REPLACEMENT_REMOVALS.items()
}
TABLES = ("row_metrics.csv", "score_improvements.csv", "normalized_learning_curves.csv")
FRACTION_MAX_DENOMINATOR = 512
FRACTION_ABS_TOLERANCE = 1e-12


def _expected_cells() -> dict[str, frozenset[tuple[str, str, str]]]:
    expected: dict[str, frozenset[tuple[str, str, str]]] = {}
    for problem, components in REPLACEMENT_COMPONENTS.items():
        axes = (
            components.representations,
            components.local_search,
            components.surrogates,
        )
        if any(len(axis) != 3 or len(set(axis)) != 3 for axis in axes):
            raise RuntimeError(f"replacement registry for {problem} is not a unique 3x3x3 design")
        expected[problem] = frozenset(product(*axes))
    return expected


EXPECTED_CELLS = _expected_cells()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _read_artifact_mapping(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    rows = _read_csv(path)
    mapping = {row["config_id"]: row for row in rows}
    if len(mapping) != len(rows):
        raise SystemExit(f"artifact mapping contains duplicate config IDs: {path}")
    return mapping


def _portable_artifact_path(mapping_path: Path, relative_path: str) -> str:
    artifact = (mapping_path.parent / relative_path).resolve()
    if not artifact.is_file():
        raise SystemExit(f"mapped artifact does not exist: {artifact}")
    try:
        return artifact.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise SystemExit(f"mapped artifact is outside the repository: {artifact}") from exc


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return f"external:{path.name}"


def _is_retained(row: dict[str, str]) -> bool:
    removed_representation, removed_local_search = REMOVED[row["problem"]]
    return (
        row["representation"] != removed_representation
        and row["local_search"] != removed_local_search
    )


def _fraction(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    result = Fraction(number).limit_denominator(FRACTION_MAX_DENOMINATOR)
    if not math.isclose(
        float(result),
        number,
        rel_tol=0.0,
        abs_tol=FRACTION_ABS_TOLERANCE,
    ):
        return ""
    return f"{result.numerator}/{result.denominator}"


def _source_fields(cohort: str) -> dict[str, str]:
    return {
        "source_cohort": cohort,
        "source_run_group": "old_81_matrix" if cohort.startswith("retained") else "delta_45_matrix",
    }


def _merge_table(
    name: str,
    retained_dir: Path,
    delta_dirs: list[Path],
    retained_ids: set[str],
) -> list[dict[str, str]]:
    retained_rows = [
        {**row, **_source_fields("retained_24h_20260709")}
        for row in _read_csv(retained_dir / name)
        if row.get("config_id") in retained_ids
    ]
    delta_rows: list[dict[str, str]] = []
    for delta_dir in delta_dirs:
        delta_rows.extend(
            {**row, **_source_fields("replacement_24h_20260711")}
            for row in _read_csv(delta_dir / name)
        )
    return retained_rows + delta_rows


def _validate_metrics(rows: list[dict[str, str]]) -> None:
    ids = [row.get("config_id", "") for row in rows]
    duplicates = sorted(config for config, count in Counter(ids).items() if count != 1)
    counts = Counter(row.get("problem", "") for row in rows)
    expected_counts = Counter(
        {problem: len(expected_cells) for problem, expected_cells in EXPECTED_CELLS.items()}
    )
    coverage_issues: list[str] = []
    config_id_mismatches: list[tuple[str, str]] = []
    for problem, expected_cells in EXPECTED_CELLS.items():
        problem_rows = [row for row in rows if row.get("problem") == problem]
        observed_counts = Counter(
            (
                row.get("representation", ""),
                row.get("local_search", ""),
                row.get("surrogate", ""),
            )
            for row in problem_rows
        )
        observed_cells = set(observed_counts)
        missing = sorted(expected_cells - observed_cells)
        unexpected = sorted(observed_cells - expected_cells)
        repeated = sorted(cell for cell, count in observed_counts.items() if count != 1)
        if missing or unexpected or repeated:
            coverage_issues.append(
                f"{problem}: missing={missing}, unexpected={unexpected}, repeated={repeated}"
            )
        for row in problem_rows:
            cell = (
                row.get("representation", ""),
                row.get("local_search", ""),
                row.get("surrogate", ""),
            )
            expected_id = "/".join((problem, *cell))
            if row.get("config_id") != expected_id:
                config_id_mismatches.append((row.get("config_id", ""), expected_id))

    expected_rows = sum(expected_counts.values())
    if (
        len(rows) != expected_rows
        or counts != expected_counts
        or duplicates
        or coverage_issues
        or config_id_mismatches
    ):
        raise SystemExit(
            "invalid final matrix: "
            f"rows={len(rows)}, counts={dict(counts)}, duplicates={duplicates}, "
            f"coverage={coverage_issues}, config_id_mismatches={config_id_mismatches}"
        )
    cohorts = Counter(row.get("source_cohort", "") for row in rows)
    if cohorts != Counter({"retained_24h_20260709": 36, "replacement_24h_20260711": 45}):
        raise SystemExit(f"invalid source cohorts: {dict(cohorts)}")


def _epoch_history(
    metrics: list[dict[str, str]], improvements: list[dict[str, str]]
) -> list[dict[str, Any]]:
    by_config: dict[str, list[dict[str, str]]] = {}
    for row in improvements:
        by_config.setdefault(row["config_id"], []).append(row)

    output: list[dict[str, Any]] = []
    for metric in sorted(metrics, key=lambda row: row["config_id"]):
        config_id = metric["config_id"]
        base = {
            key: metric[key]
            for key in (
                "config_id",
                "problem",
                "representation",
                "local_search",
                "surrogate",
                "source_cohort",
                "source_run_group",
            )
        }
        points = sorted(
            by_config.get(config_id, []),
            key=lambda row: (
                float(row.get("cumulative_model_epochs") or 0),
                float(row.get("generation") or 0),
                int(row.get("improvement_index") or 0),
            ),
        )
        initial = metric.get("initial_best_score")
        point_index = 0
        if initial not in (None, ""):
            output.append(
                {
                    **base,
                    "point_index": point_index,
                    "point_kind": "start",
                    "generation": 0,
                    "generation_fraction": 0,
                    "elapsed_seconds": 0,
                    "elapsed_fraction": 0,
                    "model_train_calls": 0,
                    "cumulative_model_epochs": 0,
                    "model_epoch_fraction": 0,
                    "best_score": initial,
                    "best_score_fraction": _fraction(initial),
                    "exact_score": initial,
                    "source_type": "initial_exact",
                    "candidate_id": "",
                    "is_final_point": False,
                }
            )
            point_index += 1
        for point in points:
            output.append(
                {
                    **base,
                    "point_index": point_index,
                    "point_kind": point.get("point_kind") or "improvement",
                    "generation": point.get("generation", ""),
                    "generation_fraction": point.get("generation_fraction", ""),
                    "elapsed_seconds": point.get("elapsed_seconds", ""),
                    "elapsed_fraction": point.get("elapsed_fraction", ""),
                    "model_train_calls": point.get("model_train_calls", ""),
                    "cumulative_model_epochs": point.get("cumulative_model_epochs", ""),
                    "model_epoch_fraction": point.get("model_epoch_fraction", ""),
                    "best_score": point.get("best_score", ""),
                    "best_score_fraction": _fraction(point.get("best_score")),
                    "exact_score": point.get("exact_score", ""),
                    "source_type": point.get("source_type", ""),
                    "candidate_id": point.get("candidate_id", ""),
                    "is_final_point": False,
                }
            )
            point_index += 1

        final_score = metric["best_score"]
        try:
            total_model_epochs = float(metric.get("total_model_epochs") or 0)
        except (TypeError, ValueError):
            total_model_epochs = 0.0
        final = {
            **base,
            "point_index": point_index,
            "point_kind": "final_endpoint",
            "generation": metric.get("completed_iterations", ""),
            "generation_fraction": 1,
            "elapsed_seconds": metric.get("elapsed_seconds", ""),
            "elapsed_fraction": 1,
            "model_train_calls": metric.get("model_train_calls", ""),
            "cumulative_model_epochs": metric.get("total_model_epochs", ""),
            "model_epoch_fraction": (
                1 if math.isfinite(total_model_epochs) and total_model_epochs > 0 else ""
            ),
            "best_score": final_score,
            "best_score_fraction": _fraction(final_score),
            "exact_score": final_score,
            "source_type": "summary_final",
            "candidate_id": metric.get("certificate_hash", ""),
            "is_final_point": True,
        }
        output.append(final)
    return output


def build(
    retained_dir: Path,
    delta_dirs: list[Path],
    out_dir: Path,
    artifact_map_path: Path | None = None,
) -> dict[str, Any]:
    old_metrics = _read_csv(retained_dir / "row_metrics.csv")
    retained_ids = {row["config_id"] for row in old_metrics if _is_retained(row)}
    if len(retained_ids) != 36:
        raise SystemExit(f"expected 36 retained cells, found {len(retained_ids)}")

    merged = {
        name: _merge_table(name, retained_dir, delta_dirs, retained_ids) for name in TABLES
    }
    metrics = merged["row_metrics.csv"]
    _validate_metrics(metrics)
    for name, rows in merged.items():
        _write_csv(out_dir / name, rows)

    artifact_mapping = _read_artifact_mapping(artifact_map_path)
    if artifact_mapping and set(artifact_mapping) != {row["config_id"] for row in metrics}:
        missing = sorted({row["config_id"] for row in metrics} - set(artifact_mapping))
        extra = sorted(set(artifact_mapping) - {row["config_id"] for row in metrics})
        raise SystemExit(f"artifact mapping coverage mismatch: missing={missing}, extra={extra}")

    public_runs = []
    for row in sorted(metrics, key=lambda item: item["config_id"]):
        public_row: dict[str, Any] = {
            **row,
            "best_score_fraction": _fraction(row.get("best_score")),
            "certificate_score_fraction": _fraction(row.get("certificate_score")),
        }
        if artifact_mapping:
            mapped = artifact_mapping[row["config_id"]]
            if mapped.get("certificate_hash") != row.get("certificate_hash"):
                raise SystemExit(f"artifact hash mismatch for {row['config_id']}")
            public_row.update(
                {
                    "source_best_certificate_path": row.get("best_certificate_path", ""),
                    "source_best_rendering_path": row.get("best_rendering_path", ""),
                    "best_certificate_path": _portable_artifact_path(
                        artifact_map_path, mapped["certificate_path"]
                    ),
                    "best_rendering_path": _portable_artifact_path(
                        artifact_map_path, mapped["rendering_path"]
                    ),
                }
            )
        public_runs.append(
            public_row
        )
    history = _epoch_history(metrics, merged["score_improvements.csv"])
    _write_csv(out_dir / "final_81_runs.csv", public_runs)
    _write_csv(out_dir / "final_81_epoch_history.csv", history)

    summary = {
        "schema": "patternboost_replacement_81_dataset_v1",
        "row_count": len(metrics),
        "epoch_history_rows": len(history),
        "problem_counts": dict(sorted(Counter(row["problem"] for row in metrics).items())),
        "source_cohorts": dict(
            sorted(Counter(row["source_cohort"] for row in metrics).items())
        ),
        "best_scores": {
            problem: max(float(row["best_score"]) for row in metrics if row["problem"] == problem)
            for problem in PROBLEMS
        },
        "retained_postprocess": _manifest_path(retained_dir),
        "delta_postprocess": [_manifest_path(path) for path in delta_dirs],
        "artifact_mapping": (
            _manifest_path(artifact_map_path) if artifact_map_path is not None else None
        ),
    }
    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retained-postprocess", type=Path, required=True)
    parser.add_argument("--delta-postprocess", type=Path, action="append", required=True)
    parser.add_argument("--artifact-map", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.retained_postprocess,
                args.delta_postprocess,
                args.out_dir,
                artifact_map_path=args.artifact_map,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
