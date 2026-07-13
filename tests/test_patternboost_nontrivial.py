from __future__ import annotations

import random
from collections import Counter

from multilevel.patternboost import (
    _certificate_failure_allows_evolution,
    _fresh_population,
    _nontrivial_certificate_ok,
    _nontrivial_constraints,
    _nontrivial_surrogate_ok,
    _select_archive_rows,
    _select_elites,
    _training_instance_ok,
)


def test_large_example_constraints_reject_small_defaults():
    assert _nontrivial_constraints("misr", 2)["min_items"] == 8
    assert _nontrivial_constraints("unit_square", 2)["min_items"] == 8
    assert _nontrivial_constraints("guillotine", 2)["min_items"] == 8


def test_requested_n_can_raise_large_example_constraints():
    assert _nontrivial_constraints("misr", 12)["min_items"] == 12
    assert _nontrivial_constraints("unit_square", 12)["min_items"] == 12
    assert _nontrivial_constraints("guillotine", 12)["min_items"] == 12


def test_training_filter_blocks_small_instances():
    misr_constraints = _nontrivial_constraints("misr", 2)
    square_constraints = _nontrivial_constraints("unit_square", 2)
    guillotine_constraints = _nontrivial_constraints("guillotine", 2)

    assert not _training_instance_ok(
        "misr",
        {"rectangles": [[idx, idx + 1, 0, 1] for idx in range(7)]},
        misr_constraints,
    )[0]
    assert _training_instance_ok(
        "misr",
        {"rectangles": [[idx, idx + 1, 0, 1] for idx in range(8)]},
        misr_constraints,
    )[0]

    assert not _training_instance_ok(
        "unit_square",
        {"squares": [[idx, 0] for idx in range(7)]},
        square_constraints,
    )[0]
    assert _training_instance_ok(
        "unit_square",
        {"squares": [[idx, 0] for idx in range(8)]},
        square_constraints,
    )[0]

    assert not _training_instance_ok(
        "guillotine",
        {"rectangles": [[idx, idx + 1, 0, 1] for idx in range(7)]},
        guillotine_constraints,
    )[0]
    assert _training_instance_ok(
        "guillotine",
        {"rectangles": [[idx, idx + 1, 0, 1] for idx in range(8)]},
        guillotine_constraints,
    )[0]


def test_square_resolution_pool_is_balanced_without_targeting_one_side():
    population = _fresh_population(
        "unit_square",
        "sqstab_exact_grid",
        random.Random(4312),
        count=128,
        n=20,
        grid=16,
        preserve_resolution_diversity=True,
    )
    assert Counter(instance["side"] for instance in population) == {1: 32, 2: 32, 3: 32, 4: 32}
    assert {len(instance["squares"]) for instance in population} == {20}


def test_square_resolution_elites_retain_every_available_resolution():
    scored = []
    for index, (score, side) in enumerate(
        [(10.0, 1), (9.0, 1), (8.0, 1), (7.0, 1), (4.0, 2), (3.0, 3), (2.0, 4)]
    ):
        scored.append((score, {"side": side, "squares": [[0, 0]]}, {}, f"id-{index}", "initial"))
    selected = _select_elites(
        scored,
        elite_size=4,
        problem="unit_square",
        representation="sqstab_exact_grid",
        preserve_resolution_diversity=True,
    )
    assert {row[1]["side"] for row in selected} == {1, 2, 3, 4}


def test_square_resolution_islands_keep_multiple_elites_and_newest_immigrant():
    scored = []
    for side in range(1, 5):
        for rank in range(4):
            candidate_id = f"side-{side}-local-{rank}"
            scored.append(
                (100.0 - 10 * side - rank, {"side": side, "squares": [[rank, side]]}, {}, candidate_id, "local_mutation")
            )
        for generation in (4, 9):
            candidate_id = f"side-{side}-immigrant-{generation}"
            scored.append(
                (
                    1.0 - generation / 100.0,
                    {"side": side, "squares": [[generation, side]], "_immigrant_generation": generation},
                    {},
                    candidate_id,
                    "random_immigrant",
                )
            )
    scored.sort(key=lambda row: row[0], reverse=True)
    selected = _select_elites(
        scored,
        elite_size=12,
        problem="unit_square",
        representation="sqstab_exact_grid",
        preserve_resolution_diversity=True,
    )
    assert Counter(row[1]["side"] for row in selected) == {1: 3, 2: 3, 3: 3, 4: 3}
    selected_ids = {row[3] for row in selected}
    for side in range(1, 5):
        assert f"side-{side}-immigrant-9" in selected_ids
        assert f"side-{side}-immigrant-4" not in selected_ids


def test_square_training_archive_round_robins_over_resolutions():
    archive = [
        (100.0 - index, {"side": side, "squares": [[index, side]]})
        for index, side in enumerate([1, 1, 1, 1, 2, 2, 3, 3, 4, 4])
    ]
    selected = _select_archive_rows(
        archive,
        limit=8,
        problem="unit_square",
        representation="sqstab_exact_grid",
        preserve_resolution_diversity=True,
    )
    assert Counter(instance["side"] for _, instance in selected) == {1: 2, 2: 2, 3: 2, 4: 2}


def test_escape_search_elites_preserve_distinct_lp_structures():
    scored = [
        (10.0, {"side": 4}, {"tau_int": 4, "tau_lp": 2.67, "lp_support": 8, "line_count": 40}, "a", "local_mutation"),
        (9.9, {"side": 4}, {"tau_int": 4, "tau_lp": 2.67, "lp_support": 8, "line_count": 41}, "b", "local_mutation"),
        (9.0, {"side": 4}, {"tau_int": 4, "tau_lp": 2.60, "lp_support": 11, "line_count": 45}, "c", "local_mutation"),
    ]
    selected = _select_elites(
        scored,
        elite_size=2,
        problem="unit_square",
        representation="sqstab_exact_grid",
        preserve_resolution_diversity=False,
        local_search="diverse_annealed_crossover",
    )
    assert [row[3] for row in selected] == ["a", "c"]


def test_subthreshold_square_can_evolve_but_cannot_be_exported():
    constraints = _nontrivial_constraints("unit_square", 20)
    instance = {"squares": [[index, 0] for index in range(20)], "side": 4}
    assert _nontrivial_surrogate_ok(
        "unit_square",
        instance,
        {"tau_int": 3},
        constraints,
    ) == (True, None)

    certificate = {"squares": instance["squares"], "tau_int": 3}
    ok, reason = _nontrivial_certificate_ok("unit_square", certificate, constraints)
    assert not ok
    assert reason == "stabbing_integer_cover_below_4"
    assert _certificate_failure_allows_evolution("unit_square", reason)
