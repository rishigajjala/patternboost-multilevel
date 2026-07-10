from __future__ import annotations

from typing import Any


def assign_pareto_ranks(family_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = list(range(len(family_rows)))
    rank = 1
    while remaining:
        frontier = [
            index
            for index in remaining
            if not any(_dominates(family_rows[other], family_rows[index]) for other in remaining if other != index)
        ]
        for index in frontier:
            family_rows[index]["evaluation"]["pareto_rank"] = rank
        remaining = [index for index in remaining if index not in frontier]
        rank += 1
    return family_rows


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_ev = left["evaluation"]
    right_ev = right["evaluation"]
    left_values = (
        -float(left_ev["invalid_rate"]),
        float(left_ev["val_mean_score"]),
        float(left_ev["test_mean_score"]),
        -float(left["complexity"]),
        float(left_ev["novelty"]),
    )
    right_values = (
        -float(right_ev["invalid_rate"]),
        float(right_ev["val_mean_score"]),
        float(right_ev["test_mean_score"]),
        -float(right["complexity"]),
        float(right_ev["novelty"]),
    )
    return all(a >= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a > b for a, b in zip(left_values, right_values, strict=True)
    )
