from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from multilevel.followup import build_followup_matrix, select_followup_cells


FIELDS = [
    "problem",
    "representation",
    "local_search",
    "surrogate",
    "control_mode",
    "rng_seed",
    "best_exact_score",
    "completed_iterations",
    "stop_reason",
    "return_code",
]


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_followup_selection_ranks_top_cells_per_problem():
    with TemporaryDirectory() as tmp:
        summary = Path(tmp) / "summary.csv"
        _write_summary(
            summary,
            [
                {
                    "problem": "misr",
                    "representation": "rect_direct",
                    "local_search": "coord_anneal",
                    "surrogate": "greedy_sampled_clique_lp",
                    "control_mode": "patternboost",
                    "rng_seed": 0,
                    "best_exact_score": 2.0,
                    "completed_iterations": 100,
                    "stop_reason": "completed",
                    "return_code": 0,
                },
                {
                    "problem": "misr",
                    "representation": "rect_direct",
                    "local_search": "coord_anneal",
                    "surrogate": "greedy_sampled_clique_lp",
                    "control_mode": "patternboost",
                    "rng_seed": 1,
                    "best_exact_score": 1.5,
                    "completed_iterations": 100,
                    "stop_reason": "completed",
                    "return_code": 0,
                },
                {
                    "problem": "misr",
                    "representation": "graph_realized",
                    "local_search": "coord_anneal",
                    "surrogate": "greedy_sampled_clique_lp",
                    "control_mode": "patternboost",
                    "rng_seed": 0,
                    "best_exact_score": 1.0,
                    "completed_iterations": 100,
                    "stop_reason": "completed",
                    "return_code": 0,
                },
                {
                    "problem": "unit_square",
                    "representation": "line_square_incidence",
                    "local_search": "coord_mutation",
                    "surrogate": "greedy_partial_lp_bitset",
                    "control_mode": "component_search",
                    "rng_seed": 0,
                    "best_exact_score": 1.2,
                    "completed_iterations": 100,
                    "stop_reason": "completed",
                    "return_code": 0,
                },
                {
                    "problem": "guillotine",
                    "representation": "recursive_obstruction_grammar",
                    "local_search": "packing_resize",
                    "surrogate": "first_cut_obstruction",
                    "control_mode": "component_search",
                    "rng_seed": 0,
                    "best_exact_score": 0.9,
                    "completed_iterations": 100,
                    "stop_reason": "completed",
                    "return_code": 0,
                },
            ],
        )
        selected = select_followup_cells(
            summary,
            top_k=1,
            control_modes=("patternboost", "component_search"),
        )
        assert [row["problem"] for row in selected] == ["misr", "unit_square", "guillotine"]
        assert selected[0]["representation"] == "rect_direct"
        assert selected[0]["source_score_mean"] == 1.75

        matrix, selection = build_followup_matrix(
            summary_csv=summary,
            stage="followup",
            budget_seconds=43200,
            git_commit="abcdef123456",
            top_k=1,
            control_modes=("patternboost", "component_search"),
        )
        assert selection == selected
        assert len(matrix) == 3
        assert {row["stage"] for row in matrix} == {"followup"}
        assert {row["budget_seconds"] for row in matrix} == {43200}
        assert all("rng_seed" in row for row in matrix)
        assert all("seed" not in row for row in matrix)
