from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from multilevel.components import COMPONENTS, fresh_rng_seed, make_run_id


DEFAULT_FOLLOWUP_MODES = ("patternboost",)


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _cell_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("problem", ""),
        row.get("representation", ""),
        row.get("local_search", ""),
        row.get("surrogate", ""),
    )


def select_followup_cells(
    summary_csv: str | Path,
    *,
    top_k: int = 3,
    problems: Iterable[str] | None = None,
    control_modes: Iterable[str] | None = None,
    min_runs: int = 1,
) -> list[dict[str, Any]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if min_runs <= 0:
        raise ValueError("min_runs must be positive")
    selected_problems = tuple(problems) if problems is not None else tuple(COMPONENTS)
    allowed_modes = tuple(control_modes) if control_modes is not None else DEFAULT_FOLLOWUP_MODES
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in _read_rows(summary_csv):
        problem = row.get("problem", "")
        if problem not in selected_problems:
            continue
        mode = row.get("control_mode", "") or "patternboost"
        if mode not in allowed_modes:
            continue
        if str(row.get("return_code", "0")) not in {"", "0"}:
            continue
        score = _float_or_none(row.get("best_exact_score"))
        if score is None:
            continue
        groups[_cell_key(row)].append(row)

    ranked_by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (problem, representation, local_search, surrogate), rows in groups.items():
        scores = [float(row["best_exact_score"]) for row in rows if _float_or_none(row.get("best_exact_score")) is not None]
        if len(scores) < min_runs:
            continue
        completed = [
            value
            for row in rows
            if (value := _float_or_none(row.get("completed_iterations"))) is not None
        ]
        budget_stopped = sum(1 for row in rows if row.get("stop_reason") == "budget_exhausted")
        ranked_by_problem[problem].append(
            {
                "problem": problem,
                "representation": representation,
                "local_search": local_search,
                "surrogate": surrogate,
                "source_runs": len(rows),
                "source_score_mean": statistics.fmean(scores),
                "source_score_median": statistics.median(scores),
                "source_score_best": max(scores),
                "source_completed_iterations_median": statistics.median(completed) if completed else None,
                "source_budget_stopped_runs": budget_stopped,
            }
        )

    selected: list[dict[str, Any]] = []
    for problem in selected_problems:
        candidates = ranked_by_problem.get(problem, [])
        candidates.sort(
            key=lambda row: (
                -float(row["source_score_mean"]),
                -float(row["source_score_best"]),
                -int(row["source_runs"]),
                row["representation"],
                row["local_search"],
                row["surrogate"],
            )
        )
        for rank, row in enumerate(candidates[:top_k], start=1):
            out = dict(row)
            out["selection_rank"] = rank
            selected.append(out)
    return selected


def build_followup_matrix(
    *,
    summary_csv: str | Path,
    stage: str,
    budget_seconds: int,
    git_commit: str,
    top_k: int = 3,
    problems: Iterable[str] | None = None,
    control_modes: Iterable[str] | None = None,
    min_runs: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = select_followup_cells(
        summary_csv,
        top_k=top_k,
        problems=problems,
        control_modes=control_modes,
        min_runs=min_runs,
    )
    rows: list[dict[str, Any]] = []
    for cell in selected:
        cell_parts = {
            "problem": cell["problem"],
            "representation": cell["representation"],
            "local_search": cell["local_search"],
            "surrogate": cell["surrogate"],
        }
        rows.append(
            {
                "schema": "run_matrix_row_v1",
                "run_id": make_run_id(
                    **cell_parts,
                    budget_seconds=budget_seconds,
                    git_commit=git_commit,
                ),
                "stage": stage,
                "rng_seed": fresh_rng_seed(),
                "budget_seconds": budget_seconds,
                "git_commit": git_commit or None,
                "selection_rank": cell["selection_rank"],
                "selection_source_runs": cell["source_runs"],
                "selection_source_score_mean": cell["source_score_mean"],
                "selection_source_score_best": cell["source_score_best"],
                **cell_parts,
            }
        )
    return rows, selected
