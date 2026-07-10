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


LARGE_EXAMPLE_CONSTRAINTS: dict[str, dict[str, int]] = {
    "misr": {"min_items": 8},
    "unit_square": {"min_items": 8, "min_tau_int": 4},
    "guillotine": {"min_items": 8, "min_destroyed": 2},
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


SYMMETRY_CROSSOVER_REPRESENTATIONS = {
    "misr": "fixed_symmetry_rectangles",
    "unit_square": "fixed_symmetry_grid",
    "guillotine": "fixed_symmetry_packing",
}


SYMMETRY_CROSSOVER_LOCAL_SEARCH = "symmetry_crossover_hillclimb"


REPLACEMENT_REMOVALS: dict[str, dict[str, str]] = {
    "misr": {
        "representation": "endpoint_sequence_pair",
        "local_search": "lp_dual_pivot",
    },
    "unit_square": {
        "representation": "square_direct",
        "local_search": "primal_dual_lines",
    },
    "guillotine": {
        "representation": "sequence_pair_packing",
        "local_search": "recursive_gadget_assembly",
    },
}


REPLACEMENT_COMPONENTS: dict[str, ProblemComponents] = {
    "misr": ProblemComponents(
        representations=(
            "triangle_free_rect",
            "quadratic_program_rectangles",
            "fixed_symmetry_rectangles",
        ),
        local_search=(
            "sequence_pair_pivot",
            "program_coeff_pivot",
            SYMMETRY_CROSSOVER_LOCAL_SEARCH,
        ),
        surrogates=COMPONENTS["misr"].surrogates,
    ),
    "unit_square": ProblemComponents(
        representations=(
            "line_square_incidence",
            "sqstab_exact_grid",
            "fixed_symmetry_grid",
        ),
        local_search=(
            "coord_mutation",
            "sqstab_local_hillclimb",
            SYMMETRY_CROSSOVER_LOCAL_SEARCH,
        ),
        surrogates=COMPONENTS["unit_square"].surrogates,
    ),
    "guillotine": ProblemComponents(
        representations=(
            "rect_direct_disjoint",
            "recursive_obstruction_grammar",
            "fixed_symmetry_packing",
        ),
        local_search=(
            "packing_resize",
            "witness_breaking",
            SYMMETRY_CROSSOVER_LOCAL_SEARCH,
        ),
        surrogates=COMPONENTS["guillotine"].surrogates,
    ),
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


def build_symmetry_crossover_matrix(
    *,
    stage: str,
    budget_seconds: int,
    git_commit: str,
    problems: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    """Build the 21-cell-per-problem symmetry/crossover experiment.

    For each problem, isolate the new local search in 3x1x3 cells, isolate the
    new representation in 1x3x3 cells, and combine both in 1x1x3 cells.
    """
    selected = tuple(problems) if problems is not None else tuple(COMPONENTS)
    rows: list[dict[str, object]] = []
    for problem in selected:
        comp = COMPONENTS[problem]
        new_representation = SYMMETRY_CROSSOVER_REPRESENTATIONS[problem]
        cells: list[tuple[str, str, str, str]] = []
        cells.extend(
            (representation, SYMMETRY_CROSSOVER_LOCAL_SEARCH, surrogate, "local_search_only")
            for representation, surrogate in product(comp.representations, comp.surrogates)
        )
        cells.extend(
            (new_representation, local_search, surrogate, "representation_only")
            for local_search, surrogate in product(comp.local_search, comp.surrogates)
        )
        cells.extend(
            (new_representation, SYMMETRY_CROSSOVER_LOCAL_SEARCH, surrogate, "combined")
            for surrogate in comp.surrogates
        )
        for representation, local_search, surrogate, experiment_group in cells:
            cell = {
                "problem": problem,
                "representation": representation,
                "local_search": local_search,
                "surrogate": surrogate,
            }
            rows.append(
                {
                    "schema": "run_matrix_row_v1",
                    "run_id": make_run_id(
                        **cell,
                        budget_seconds=budget_seconds,
                        git_commit=git_commit,
                    ),
                    "stage": stage,
                    "rng_seed": fresh_rng_seed(),
                    "budget_seconds": budget_seconds,
                    "git_commit": git_commit or None,
                    "experiment_family": "symmetry_crossover_v1",
                    "experiment_group": experiment_group,
                    **cell,
                }
            )
    return rows


def build_replacement_delta_matrix(
    *,
    stage: str,
    budget_seconds: int,
    git_commit: str,
    problems: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    """Build only the 15 changed cells in each replacement 3x3x3 table."""
    selected = tuple(problems) if problems is not None else tuple(REPLACEMENT_COMPONENTS)
    rows: list[dict[str, object]] = []
    for problem in selected:
        if problem not in REPLACEMENT_COMPONENTS:
            raise ValueError(f"no replacement design for problem: {problem}")
        old = COMPONENTS[problem]
        new = REPLACEMENT_COMPONENTS[problem]
        added_representations = set(new.representations) - set(old.representations)
        added_local_search = set(new.local_search) - set(old.local_search)
        if len(added_representations) != 1 or len(added_local_search) != 1:
            raise ValueError(f"replacement design for {problem} must add one representation and one local search")
        new_representation = next(iter(added_representations))
        new_local_search = next(iter(added_local_search))
        for representation, local_search, surrogate in product(
            new.representations,
            new.local_search,
            new.surrogates,
        ):
            if representation != new_representation and local_search != new_local_search:
                continue
            if representation == new_representation and local_search == new_local_search:
                experiment_group = "combined"
            elif representation == new_representation:
                experiment_group = "representation_only"
            else:
                experiment_group = "local_search_only"
            cell = {
                "problem": problem,
                "representation": representation,
                "local_search": local_search,
                "surrogate": surrogate,
            }
            rows.append(
                {
                    "schema": "run_matrix_row_v1",
                    "run_id": make_run_id(
                        **cell,
                        budget_seconds=budget_seconds,
                        git_commit=git_commit,
                    ),
                    "stage": stage,
                    "rng_seed": fresh_rng_seed(),
                    "budget_seconds": budget_seconds,
                    "git_commit": git_commit or None,
                    "experiment_family": "replacement_delta_v1",
                    "experiment_group": experiment_group,
                    "removed_representation": REPLACEMENT_REMOVALS[problem]["representation"],
                    "removed_local_search": REPLACEMENT_REMOVALS[problem]["local_search"],
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
