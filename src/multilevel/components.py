from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from secrets import randbits
from typing import Iterable


@dataclass(frozen=True)
class ProblemComponents:
    representations: tuple[str, ...]
    local_search: tuple[str, ...]
    surrogates: tuple[str, ...]


COMPONENTS: dict[str, ProblemComponents] = {
    "misr": ProblemComponents(
        representations=("endpoint_sequence_pair", "triangle_free_rect", "quadratic_program_rectangles"),
        local_search=("sequence_pair_pivot", "lp_dual_pivot", "program_coeff_pivot"),
        surrogates=(
            "exact_lp_gap_pressure",
            "triangle_free_exact_gap_pressure",
            "graph_conflict_proxy",
        ),
    ),
    "unit_square": ProblemComponents(
        representations=("square_direct", "line_square_incidence", "sqstab_exact_grid"),
        local_search=("coord_mutation", "primal_dual_lines", "sqstab_local_hillclimb"),
        surrogates=(
            "greedy_partial_lp_bitset",
            "exact_stab_gap_pressure",
            "incidence_statistics",
        ),
    ),
    "guillotine": ProblemComponents(
        representations=(
            "rect_direct_disjoint",
            "sequence_pair_packing",
            "recursive_obstruction_grammar",
        ),
        local_search=("packing_resize", "recursive_gadget_assembly", "witness_breaking"),
        surrogates=(
            "first_cut_obstruction",
            "depth_limited_dp",
            "k_subset_nonseparability",
        ),
    ),
}


DEFAULT_STAGE_BUDGETS = {
    "pilot": 3600,
    "main": 3 * 3600,
    "followup": 12 * 3600,
    "audit": 0,
    "controls": 3 * 3600,
}


CONTROL_MODES = (
    "local_only",
    "model_only_weak_local",
    "shuffled_label",
)


CONTROL_BASE_CELLS: dict[str, dict[str, str]] = {
    "misr": {
        "representation": "quadratic_program_rectangles",
        "local_search": "program_coeff_pivot",
        "surrogate": "triangle_free_exact_gap_pressure",
    },
    "unit_square": {
        "representation": "sqstab_exact_grid",
        "local_search": "sqstab_local_hillclimb",
        "surrogate": "exact_stab_gap_pressure",
    },
    "guillotine": {
        "representation": "recursive_obstruction_grammar",
        "local_search": "witness_breaking",
        "surrogate": "k_subset_nonseparability",
    },
}


def iter_cells(problems: Iterable[str] | None = None):
    selected = tuple(problems) if problems is not None else tuple(COMPONENTS)
    for problem in selected:
        comp = COMPONENTS[problem]
        for representation, local_search, surrogate in product(
            comp.representations, comp.local_search, comp.surrogates
        ):
            yield {
                "problem": problem,
                "representation": representation,
                "local_search": local_search,
                "surrogate": surrogate,
            }


def make_run_id(
    *,
    problem: str,
    representation: str,
    local_search: str,
    surrogate: str,
    budget_seconds: int,
    git_commit: str,
) -> str:
    short_git = git_commit[:12] if git_commit else "nogit"
    return (
        f"{problem}/{representation}/{local_search}/{surrogate}/"
        f"budget{budget_seconds}/git{short_git}"
    )


def make_control_run_id(
    *,
    problem: str,
    representation: str,
    local_search: str,
    surrogate: str,
    control_mode: str,
    budget_seconds: int,
    git_commit: str,
) -> str:
    short_git = git_commit[:12] if git_commit else "nogit"
    return (
        f"control/{control_mode}/{problem}/{representation}/{local_search}/{surrogate}/"
        f"budget{budget_seconds}/git{short_git}"
    )


def fresh_rng_seed() -> int:
    return randbits(63)


def build_matrix(
    *,
    stage: str,
    budget_seconds: int,
    git_commit: str,
    problems: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cell in iter_cells(problems):
        run_id = make_run_id(
            **cell,
            budget_seconds=budget_seconds,
            git_commit=git_commit,
        )
        rows.append(
            {
                "schema": "run_matrix_row_v1",
                "run_id": run_id,
                "stage": stage,
                "rng_seed": fresh_rng_seed(),
                "budget_seconds": budget_seconds,
                "git_commit": git_commit or None,
                **cell,
            }
        )
    return rows


def build_control_matrix(
    *,
    stage: str,
    budget_seconds: int,
    git_commit: str,
    problems: Iterable[str] | None = None,
    control_modes: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    selected_problems = tuple(problems) if problems is not None else tuple(CONTROL_BASE_CELLS)
    selected_modes = tuple(control_modes) if control_modes is not None else CONTROL_MODES
    rows: list[dict[str, object]] = []
    for problem in selected_problems:
        if problem not in CONTROL_BASE_CELLS:
            raise ValueError(f"no default control cell for problem: {problem}")
        cell = CONTROL_BASE_CELLS[problem]
        for mode in selected_modes:
            if mode not in CONTROL_MODES:
                raise ValueError(f"unknown control mode: {mode}")
            run_id = make_control_run_id(
                problem=problem,
                representation=cell["representation"],
                local_search=cell["local_search"],
                surrogate=cell["surrogate"],
                control_mode=mode,
                budget_seconds=budget_seconds,
                git_commit=git_commit,
            )
            rows.append(
                {
                    "schema": "control_matrix_row_v1",
                    "run_id": run_id,
                    "stage": stage,
                    "rng_seed": fresh_rng_seed(),
                    "budget_seconds": budget_seconds,
                    "git_commit": git_commit or None,
                    "control_mode": mode,
                    "problem": problem,
                    **cell,
                }
            )
    return rows
