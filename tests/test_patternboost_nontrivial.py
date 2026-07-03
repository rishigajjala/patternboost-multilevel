from __future__ import annotations

from multilevel.patternboost import _nontrivial_constraints, _training_instance_ok


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
