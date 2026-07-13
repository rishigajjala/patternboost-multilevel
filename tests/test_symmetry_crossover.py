from __future__ import annotations

import random
from collections import Counter
from itertools import product

from multilevel.components import (
    COMPONENTS,
    REPLACEMENT_COMPONENTS,
    REPLACEMENT_REMOVALS,
    REPLACEMENT_RUNTIME_PARAMETERS,
    REPLACEMENT_RUNTIME_OVERRIDES,
    SYMMETRY_CROSSOVER_LOCAL_SEARCH,
    SYMMETRY_CROSSOVER_REPRESENTATIONS,
    UNIT_SQUARE_ESCAPE_LOCAL_SEARCH,
    build_replacement_delta_matrix,
    build_symmetry_crossover_matrix,
    build_unit_square_restart_matrix,
)
from multilevel.mutations import _exact_hillclimb_key, mutate_instance
from multilevel.representations import (
    decoded_geometry,
    initial_instance_for_representation,
    repair_instance_for_representation,
)
from multilevel.scorers import guillotine, misr, unit_square


SCORERS = {"misr": misr, "unit_square": unit_square, "guillotine": guillotine}
OBJECT_KEYS = {"misr": "rectangles", "unit_square": "squares", "guillotine": "rectangles"}


def test_symmetry_crossover_matrix_has_requested_63_cells():
    rows = build_symmetry_crossover_matrix(
        stage="pilot",
        budget_seconds=60,
        git_commit="abc123",
    )
    assert len(rows) == 63
    assert Counter(row["problem"] for row in rows) == {
        "misr": 21,
        "unit_square": 21,
        "guillotine": 21,
    }
    for problem in SCORERS:
        problem_rows = [row for row in rows if row["problem"] == problem]
        assert Counter(row["experiment_group"] for row in problem_rows) == {
            "local_search_only": 9,
            "representation_only": 9,
            "combined": 3,
        }


def test_replacement_delta_has_15_changed_cells_per_problem():
    rows = build_replacement_delta_matrix(
        stage="main",
        budget_seconds=24 * 3600,
        git_commit="abc123",
    )
    assert len(rows) == 45
    assert Counter(row["problem"] for row in rows) == {
        "misr": 15,
        "unit_square": 15,
        "guillotine": 15,
    }
    for problem in REPLACEMENT_COMPONENTS:
        problem_rows = [row for row in rows if row["problem"] == problem]
        assert Counter(row["experiment_group"] for row in problem_rows) == {
            "local_search_only": 6,
            "representation_only": 6,
            "combined": 3,
        }


def test_replacement_delta_and_retained_cells_form_full_3x3x3_tables():
    rows = build_replacement_delta_matrix(stage="main", budget_seconds=60, git_commit="abc123")
    for problem, replacement in REPLACEMENT_COMPONENTS.items():
        old = COMPONENTS[problem]
        removed = REPLACEMENT_REMOVALS[problem]
        retained_representations = set(old.representations) - {removed["representation"]}
        retained_local_search = set(old.local_search) - {removed["local_search"]}
        retained_cells = {
            (representation, local_search, surrogate)
            for representation, local_search, surrogate in product(
                retained_representations,
                retained_local_search,
                old.surrogates,
            )
        }
        delta_cells = {
            (row["representation"], row["local_search"], row["surrogate"])
            for row in rows
            if row["problem"] == problem
        }
        full_cells = {
            (representation, local_search, surrogate)
            for representation, local_search, surrogate in product(
                replacement.representations,
                replacement.local_search,
                replacement.surrogates,
            )
        }
        assert len(retained_cells) == 12
        assert len(delta_cells) == 15
        assert retained_cells.isdisjoint(delta_cells)
        assert retained_cells | delta_cells == full_cells
        assert len(full_cells) == 27


def test_replacement_delta_embeds_successful_probe_runtime():
    rows = build_replacement_delta_matrix(stage="main", budget_seconds=24 * 3600, git_commit="abc123")
    for row in rows:
        expected_runtime = dict(REPLACEMENT_RUNTIME_PARAMETERS)
        expected_runtime.update(REPLACEMENT_RUNTIME_OVERRIDES.get(row["problem"], {}))
        for key, expected in expected_runtime.items():
            assert row[key] == expected
        assert row["experiment_family"] == "replacement_delta_v3_resolution_diverse"

    for problem, expected_n, expected_grid in (
        ("misr", 12, 8),
        ("unit_square", 20, 16),
        ("guillotine", 12, 8),
    ):
        problem_rows = [row for row in rows if row["problem"] == problem]
        assert len(problem_rows) == 15
        assert {row["n"] for row in problem_rows} == {expected_n}
        assert {row["grid"] for row in problem_rows} == {expected_grid}
        assert {row["population"] for row in problem_rows} == ({32} if problem == "unit_square" else {16})
        assert {row["elite"] for row in problem_rows} == ({12} if problem == "unit_square" else {4})
        assert {row["train_every"] for row in problem_rows} == {10}


def test_fixed_symmetry_representations_preserve_cardinality_and_score():
    for offset, problem in enumerate(SCORERS):
        representation = SYMMETRY_CROSSOVER_REPRESENTATIONS[problem]
        instance = initial_instance_for_representation(
            problem,
            representation,
            random.Random(9100 + offset),
            n=8,
            grid=8,
        )
        repaired = repair_instance_for_representation(
            problem,
            representation,
            instance,
            grid=8,
            n_min=8,
            n_max=24,
        )
        geometry = decoded_geometry(repaired)
        assert len(geometry[OBJECT_KEYS[problem]]) == 8
        if problem == "unit_square":
            assert geometry["side"] == 2
        certificate = SCORERS[problem].score_instance(geometry)
        assert certificate["solver_status"] == "optimal"


def test_fixed_symmetry_grid_repair_restores_fixed_common_side():
    representation = SYMMETRY_CROSSOVER_REPRESENTATIONS["unit_square"]
    instance = initial_instance_for_representation(
        "unit_square",
        representation,
        random.Random(9150),
        n=8,
        grid=8,
    )
    instance["side"] = 4
    instance["_representation_payload"]["side"] = 4

    repaired = repair_instance_for_representation(
        "unit_square",
        representation,
        instance,
        grid=8,
        n_min=8,
        n_max=24,
    )

    assert repaired["side"] == 2
    assert repaired["_representation_payload"]["side"] == 2
    assert repaired["_representation_payload"]["side_rule"] == "fixed_Q2"


def test_symmetry_crossover_hillclimb_is_exact_nonworsening():
    cases = (
        ("misr", "triangle_free_rect"),
        ("unit_square", "fixed_symmetry_grid"),
        ("guillotine", "fixed_symmetry_packing"),
    )
    for offset, (problem, representation) in enumerate(cases):
        rng = random.Random(9200 + offset)
        instance = initial_instance_for_representation(problem, representation, rng, n=8, grid=8)
        before = SCORERS[problem].score_instance(decoded_geometry(instance))
        child = mutate_instance(
            problem,
            SYMMETRY_CROSSOVER_LOCAL_SEARCH,
            instance,
            rng,
            grid=8,
            n_min=8,
            n_max=24,
            representation=representation,
        )
        after = SCORERS[problem].score_instance(decoded_geometry(child))
        assert float(after["score"]) + 1e-12 >= float(before["score"])
        assert child["_local_search_payload"]["steps"] == 25
        assert child["_local_search_payload"]["move_probabilities"] == {
            "shift": 0.55,
            "random_move": 0.25,
            "crossover": 0.10,
            "symmetry": 0.10,
        }


def test_exact_hillclimb_prioritizes_admissible_square_instances():
    admissible = {
        "schema": "unit_square_instance_v1",
        "squares": [[3 * idx, 3 * idx] for idx in range(8)],
        "side": 1,
    }
    high_ratio_but_small_cover = {
        "schema": "unit_square_instance_v1",
        "squares": [[0, 1], [1, 0], [1, 3], [3, 1]],
        "side": 2,
    }
    admissible_key = _exact_hillclimb_key("unit_square", admissible)
    small_cover_key = _exact_hillclimb_key("unit_square", high_ratio_but_small_cover)
    assert admissible_key[0] == 1.0
    assert small_cover_key[0] == 0.0
    assert admissible_key > small_cover_key


def test_unit_square_restart_matrix_is_fresh_target_free_and_six_rows():
    rows = build_unit_square_restart_matrix(
        stage="restart",
        budget_seconds=24 * 3600,
        git_commit="abc123",
    )
    assert len(rows) == 6
    assert len({row["rng_seed"] for row in rows}) == 6
    assert {row["experiment_arm"] for row in rows} == {"compact", "scaled"}
    assert all(row["fresh_start"] is True for row in rows)
    assert all("reference_score" not in row for row in rows)
    escape_rows = [row for row in rows if row["selection_rank"] == 1]
    assert len(escape_rows) == 2
    assert {row["local_search"] for row in escape_rows} == {UNIT_SQUARE_ESCAPE_LOCAL_SEARCH}
    assert {row["population"] for row in escape_rows} == {48}
    assert {row["elite"] for row in escape_rows} == {16}
    assert {row["initial_pool_size"] for row in escape_rows} == {512, 1024}


def test_diverse_annealed_square_search_retains_parent_or_better():
    rng = random.Random(9300)
    parent = initial_instance_for_representation(
        "unit_square", "sqstab_exact_grid", rng, n=8, grid=8
    )
    mate = initial_instance_for_representation(
        "unit_square", "sqstab_exact_grid", rng, n=8, grid=8
    )
    mate["side"] = parent["side"]
    mate["_representation_payload"]["side"] = parent["side"]
    before = unit_square.score_instance(decoded_geometry(parent))
    child = mutate_instance(
        "unit_square",
        UNIT_SQUARE_ESCAPE_LOCAL_SEARCH,
        parent,
        rng,
        grid=8,
        n_min=8,
        n_max=24,
        representation="sqstab_exact_grid",
        mate=mate,
    )
    after = unit_square.score_instance(decoded_geometry(child))
    assert float(after["score"]) + 1e-12 >= float(before["score"])
    payload = child["_local_search_payload"]
    assert payload["algorithm"] == UNIT_SQUARE_ESCAPE_LOCAL_SEARCH
    assert payload["steps"] == 32
    assert payload["acceptance"] == "exact_simulated_annealing_with_best_retention"
