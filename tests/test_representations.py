from __future__ import annotations

import random

from multilevel.components import COMPONENTS
from multilevel.mutations import mutate_instance
from multilevel.representations import (
    decoded_geometry,
    initial_instance_for_representation,
    repair_instance_for_representation,
)
from multilevel.scorers import guillotine, misr, unit_square


SCORERS = {
    "misr": misr,
    "unit_square": unit_square,
    "guillotine": guillotine,
}


def test_registered_representations_repair_and_mutate_to_valid_geometry():
    rng = random.Random(20260625)
    for problem, components in COMPONENTS.items():
        for representation in components.representations:
            instance = initial_instance_for_representation(problem, representation, rng, n=5, grid=5)
            repaired = repair_instance_for_representation(
                problem,
                representation,
                instance,
                grid=5,
                n_min=2,
                n_max=12,
            )
            assert repaired["_representation"] == representation
            assert repaired["_representation_payload"]
            SCORERS[problem].score_instance(decoded_geometry(repaired))

            for local_search in components.local_search:
                child = mutate_instance(
                    problem,
                    local_search,
                    repaired,
                    rng,
                    grid=5,
                    n_min=2,
                    n_max=12,
                    representation=representation,
                )
                assert child["_representation"] == representation
                assert child["_representation_payload"]
                SCORERS[problem].score_instance(decoded_geometry(child))


def test_triangle_free_misr_representation_stays_triangle_free():
    rng = random.Random(20260625)
    representation = "triangle_free_rect"
    instance = initial_instance_for_representation("misr", representation, rng, n=12, grid=8)

    for local_search in ("coord_anneal", "lp_dual_pivot", "motif_blowup"):
        repaired = repair_instance_for_representation(
            "misr",
            representation,
            instance,
            grid=8,
            n_min=3,
            n_max=24,
        )
        geometry = decoded_geometry(repaired)
        cert = misr.score_instance(geometry)
        assert geometry["constraints"]["triangle_free"] is True
        assert cert["triangle_free"] is True
        assert cert["max_clique_size"] <= 2

        instance = mutate_instance(
            "misr",
            local_search,
            repaired,
            rng,
            grid=8,
            n_min=3,
            n_max=24,
            representation=representation,
        )


def test_quadratic_program_misr_representation_stays_triangle_free():
    rng = random.Random(20260630)
    representation = "quadratic_program_rectangles"
    instance = initial_instance_for_representation("misr", representation, rng, n=10, grid=8)

    for _ in range(5):
        repaired = repair_instance_for_representation(
            "misr",
            representation,
            instance,
            grid=8,
            n_min=3,
            n_max=24,
        )
        geometry = decoded_geometry(repaired)
        cert = misr.score_instance(geometry)
        assert geometry["constraints"]["triangle_free"] is True
        assert cert["triangle_free"] is True

        instance = mutate_instance(
            "misr",
            "program_coeff_pivot",
            repaired,
            rng,
            grid=8,
            n_min=3,
            n_max=24,
            representation=representation,
        )


def test_sqstab_exact_grid_representation_generates_random_instances():
    rng = random.Random(20260630)
    representation = "sqstab_exact_grid"
    instance = initial_instance_for_representation("unit_square", representation, rng, n=8, grid=5)
    other = initial_instance_for_representation("unit_square", representation, random.Random(20260631), n=8, grid=5)
    cert = unit_square.score_instance(decoded_geometry(instance))
    assert 1 <= decoded_geometry(instance)["side"] <= 4
    assert decoded_geometry(instance)["squares"] != decoded_geometry(other)["squares"]
    assert cert["solver_status"] == "optimal"


def test_recursive_guillotine_representation_generates_valid_random_obstruction():
    rng = random.Random(20260625)
    instance = initial_instance_for_representation(
        "guillotine",
        "recursive_obstruction_grammar",
        rng,
        n=12,
        grid=8,
    )
    cert = guillotine.score_instance(decoded_geometry(instance))
    assert cert["solver_status"] == "optimal"
    assert cert["n"] >= 1
    assert "threshold_nonseparable_fraction" in cert


def test_recursive_guillotine_obstruction_is_large_nontrivial_family():
    first = decoded_geometry(
        initial_instance_for_representation(
            "guillotine",
            "recursive_obstruction_grammar",
            random.Random(20260703),
            n=14,
            grid=8,
        )
    )
    second = decoded_geometry(
        initial_instance_for_representation(
            "guillotine",
            "recursive_obstruction_grammar",
            random.Random(20260704),
            n=14,
            grid=8,
        )
    )
    cert = guillotine.score_instance(first)
    assert first["rectangles"] != second["rectangles"]
    assert cert["n"] == 14
    assert cert["destroyed"] >= 2
