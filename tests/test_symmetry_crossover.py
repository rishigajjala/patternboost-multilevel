from __future__ import annotations

import random
from collections import Counter

from multilevel.components import (
    SYMMETRY_CROSSOVER_LOCAL_SEARCH,
    SYMMETRY_CROSSOVER_REPRESENTATIONS,
    build_symmetry_crossover_matrix,
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
