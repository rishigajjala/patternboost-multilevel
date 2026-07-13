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
UNIT_SQUARE_ESCAPE_LOCAL_SEARCH = "diverse_annealed_crossover"


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


REPLACEMENT_RUNTIME_PARAMETERS: dict[str, int] = {
    "n": 12,
    "grid": 8,
    "iterations": 1_000_000,
    "population": 16,
    "elite": 4,
    "exact_every": 5,
    "train_every": 10,
    "model_samples": 16,
    "model_epochs": 3,
    "block_size": 128,
    "checkpoint_every": 1,
}

UNIT_SQUARE_DIVERSITY_PARAMETERS: dict[str, int | bool] = {
    "population": 32,
    "elite": 12,
    "initial_pool_size": 128,
    "immigrants_per_generation": 4,
    "preserve_resolution_diversity": True,
}

REPLACEMENT_RUNTIME_OVERRIDES: dict[str, dict[str, int | bool]] = {
    "unit_square": {
        "n": 20,
        "grid": 16,
        **UNIT_SQUARE_DIVERSITY_PARAMETERS,
    },
}


# Highest-scoring cells in the final 81-cell table. Ties are resolved
# lexicographically by configuration ID. The winning unit-square cell retains
# its diversity-island runtime settings in both capacity arms.
MODEL_CAPACITY_TOP_CONFIGS: dict[str, tuple[dict[str, object], ...]] = {
    "misr": (
        {
            "representation": "triangle_free_rect",
            "local_search": "sequence_pair_pivot",
            "surrogate": "exact_lp_gap_pressure",
            "reference_score": 1.5,
            "reference_score_fraction": "3/2",
        },
        {
            "representation": "triangle_free_rect",
            "local_search": "program_coeff_pivot",
            "surrogate": "exact_lp_gap_pressure",
            "reference_score": 1.4,
            "reference_score_fraction": "7/5",
        },
        {
            "representation": "triangle_free_rect",
            "local_search": "program_coeff_pivot",
            "surrogate": "triangle_free_exact_gap_pressure",
            "reference_score": 1.375,
            "reference_score_fraction": "11/8",
        },
    ),
    "unit_square": (
        {
            "representation": "sqstab_exact_grid",
            "local_search": "symmetry_crossover_hillclimb",
            "surrogate": "exact_stab_gap_pressure",
            "reference_score": 20 / 13,
            "reference_score_fraction": "20/13",
            "runtime_overrides": {
                "population": 32,
                "elite": 12,
                "immigrants_per_generation": 4,
                "preserve_resolution_diversity": True,
            },
            "compact_initial_pool_size": 128,
            "compact_training_archive_limit": 96,
        },
        {
            "representation": "fixed_symmetry_grid",
            "local_search": "coord_mutation",
            "surrogate": "exact_stab_gap_pressure",
            "reference_score": 1.5,
            "reference_score_fraction": "3/2",
        },
        {
            "representation": "fixed_symmetry_grid",
            "local_search": "symmetry_crossover_hillclimb",
            "surrogate": "exact_stab_gap_pressure",
            "reference_score": 1.5,
            "reference_score_fraction": "3/2",
        },
    ),
    "guillotine": (
        {
            "representation": "rect_direct_disjoint",
            "local_search": "witness_breaking",
            "surrogate": "depth_limited_dp",
            "reference_score": 1 / 3,
            "reference_score_fraction": "1/3",
        },
        {
            "representation": "rect_direct_disjoint",
            "local_search": "packing_resize",
            "surrogate": "depth_limited_dp",
            "reference_score": 3 / 11,
            "reference_score_fraction": "3/11",
        },
        {
            "representation": "rect_direct_disjoint",
            "local_search": "witness_breaking",
            "surrogate": "first_cut_obstruction",
            "reference_score": 3 / 11,
            "reference_score_fraction": "3/11",
        },
    ),
}


MODEL_CAPACITY_ARMS: dict[str, dict[str, int | float]] = {
    "compact": {
        "initial_pool_size": 32,
        "training_archive_limit": 48,
        "model_embed_dim": 96,
        "model_num_heads": 4,
        "model_num_layers": 2,
    },
    "scaled": {
        "initial_pool_size": 256,
        "training_archive_limit": 256,
        "model_embed_dim": 192,
        "model_num_heads": 8,
        "model_num_layers": 4,
    },
}


MODEL_CAPACITY_RUNTIME_PARAMETERS: dict[str, int | float | str | bool] = {
    "iterations": 1_000_000,
    "population": 32,
    "elite": 6,
    "exact_every": 5,
    "train_every": 10,
    "model_samples": 16,
    "model_kind": "transformer",
    "model_epochs": 3,
    "block_size": 128,
    "model_batch_size": 32,
    "model_learning_rate": 3e-4,
    "checkpoint_every": 1,
    "immigrants_per_generation": 0,
    "preserve_resolution_diversity": False,
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


def build_model_capacity_matrix(
    *,
    stage: str,
    budget_seconds: int,
    git_commit: str,
    problems: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    """Build matched compact-versus-scaled rows for the top automated cells."""
    selected = tuple(problems) if problems is not None else tuple(MODEL_CAPACITY_TOP_CONFIGS)
    unknown = sorted(set(selected) - set(MODEL_CAPACITY_TOP_CONFIGS))
    if unknown:
        raise ValueError(f"model-capacity experiment has no selected cells for: {', '.join(unknown)}")

    short_git = git_commit[:12] if git_commit else "nogit"
    rows: list[dict[str, object]] = []
    for problem in selected:
        n = 20 if problem == "unit_square" else 12
        grid = 16 if problem == "unit_square" else 8
        for rank, selected_cell in enumerate(MODEL_CAPACITY_TOP_CONFIGS[problem], start=1):
            cell = {
                "problem": problem,
                "representation": str(selected_cell["representation"]),
                "local_search": str(selected_cell["local_search"]),
                "surrogate": str(selected_cell["surrogate"]),
            }
            for arm, arm_parameters in MODEL_CAPACITY_ARMS.items():
                selected_arm_parameters = dict(arm_parameters)
                if arm == "compact":
                    selected_arm_parameters["initial_pool_size"] = int(
                        selected_cell.get("compact_initial_pool_size", selected_arm_parameters["initial_pool_size"])
                    )
                    selected_arm_parameters["training_archive_limit"] = int(
                        selected_cell.get(
                            "compact_training_archive_limit",
                            selected_arm_parameters["training_archive_limit"],
                        )
                    )
                runtime_overrides = dict(selected_cell.get("runtime_overrides", {}))
                rows.append(
                    {
                        "schema": "run_matrix_row_v1",
                        "run_id": (
                            f"capacity/{arm}/{problem}/{cell['representation']}/"
                            f"{cell['local_search']}/{cell['surrogate']}/"
                            f"budget{budget_seconds}/git{short_git}"
                        ),
                        "stage": stage,
                        "rng_seed": fresh_rng_seed(),
                        "budget_seconds": budget_seconds,
                        "git_commit": git_commit or None,
                        "experiment_family": "model_capacity_v1",
                        "experiment_arm": arm,
                        "selection_rank": rank,
                        "selection_rule": "top_final_score_then_config_id",
                        "reference_score": selected_cell["reference_score"],
                        "reference_score_fraction": selected_cell["reference_score_fraction"],
                        "n": n,
                        "grid": grid,
                        **MODEL_CAPACITY_RUNTIME_PARAMETERS,
                        **runtime_overrides,
                        **selected_arm_parameters,
                        **cell,
                    }
                )
    return rows


def build_unit_square_restart_matrix(
    *,
    stage: str,
    budget_seconds: int,
    git_commit: str,
) -> list[dict[str, object]]:
    """Build six fresh unit-square rows without a target score in the matrix."""
    rows = build_model_capacity_matrix(
        stage=stage,
        budget_seconds=budget_seconds,
        git_commit=git_commit,
        problems=("unit_square",),
    )
    short_git = git_commit[:12] if git_commit else "nogit"
    for row in rows:
        row["experiment_family"] = "unit_square_fresh_restart_v1"
        row["fresh_start"] = True
        row["selection_rule"] = "restart_prior_capacity_cells_without_target_value"
        row.pop("reference_score", None)
        row.pop("reference_score_fraction", None)
        if int(row["selection_rank"]) == 1:
            row["local_search"] = UNIT_SQUARE_ESCAPE_LOCAL_SEARCH
            row["population"] = 48
            row["elite"] = 16
            row["immigrants_per_generation"] = 8
            row["preserve_resolution_diversity"] = True
            if row["experiment_arm"] == "compact":
                row["initial_pool_size"] = 512
                row["training_archive_limit"] = 192
            else:
                row["initial_pool_size"] = 1024
                row["training_archive_limit"] = 512
        row["run_id"] = (
            f"unit_square_restart/{row['experiment_arm']}/{row['selection_rank']}/"
            f"{row['representation']}/{row['local_search']}/{row['surrogate']}/"
            f"budget{budget_seconds}/git{short_git}"
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
            runtime = dict(REPLACEMENT_RUNTIME_PARAMETERS)
            runtime.update(REPLACEMENT_RUNTIME_OVERRIDES.get(problem, {}))
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
                    "experiment_family": "replacement_delta_v3_resolution_diverse",
                    "experiment_group": experiment_group,
                    "removed_representation": REPLACEMENT_REMOVALS[problem]["representation"],
                    "removed_local_search": REPLACEMENT_REMOVALS[problem]["local_search"],
                    **runtime,
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
