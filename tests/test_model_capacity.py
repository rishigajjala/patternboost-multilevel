from __future__ import annotations

from collections import Counter

from multilevel import components


def test_model_capacity_matrix_is_matched_and_separates_output_arms(monkeypatch):
    next_seed = iter(range(100, 118))
    monkeypatch.setattr(components, "fresh_rng_seed", lambda: next(next_seed))

    rows = components.build_model_capacity_matrix(
        stage="model_capacity",
        budget_seconds=7200,
        git_commit="abcdef1234567890",
    )

    assert len(rows) == 18
    assert {row["experiment_arm"] for row in rows} == {"compact", "scaled"}
    assert len({row["rng_seed"] for row in rows}) == 18
    assert all(row["population"] == 32 for row in rows)
    assert all(row["model_samples"] == 16 for row in rows)

    diversity_rows = [row for row in rows if row["preserve_resolution_diversity"]]
    assert len(diversity_rows) == 2
    assert all(row["problem"] == "unit_square" and row["selection_rank"] == 1 for row in diversity_rows)
    assert all(row["elite"] == 12 for row in diversity_rows)
    assert {row["reference_score_fraction"] for row in diversity_rows} == {"20/13"}
    diversity_by_arm = {row["experiment_arm"]: row for row in diversity_rows}
    assert diversity_by_arm["compact"]["initial_pool_size"] == 128
    assert diversity_by_arm["compact"]["training_archive_limit"] == 96
    assert diversity_by_arm["scaled"]["initial_pool_size"] == 256
    assert diversity_by_arm["scaled"]["training_archive_limit"] == 256
    assert all(row["elite"] == 6 for row in rows if row not in diversity_rows)

    unit_compact = sorted(
        (row for row in rows if row["problem"] == "unit_square" and row["experiment_arm"] == "compact"),
        key=lambda row: row["selection_rank"],
    )
    assert [
        (row["representation"], row["local_search"], row["surrogate"])
        for row in unit_compact
    ] == [
        ("sqstab_exact_grid", "symmetry_crossover_hillclimb", "exact_stab_gap_pressure"),
        ("fixed_symmetry_grid", "coord_mutation", "exact_stab_gap_pressure"),
        ("fixed_symmetry_grid", "symmetry_crossover_hillclimb", "exact_stab_gap_pressure"),
    ]

    keys = Counter(
        (row["problem"], row["representation"], row["local_search"], row["surrogate"])
        for row in rows
    )
    assert set(keys.values()) == {2}

    compact = next(row for row in rows if row["experiment_arm"] == "compact")
    scaled = next(
        row
        for row in rows
        if row["experiment_arm"] == "scaled"
        and row["problem"] == compact["problem"]
        and row["selection_rank"] == compact["selection_rank"]
    )
    assert compact["model_num_layers"] == 2
    assert scaled["model_num_layers"] == 4
    expected_compact_archive = 96 if compact["preserve_resolution_diversity"] else 48
    assert compact["training_archive_limit"] == expected_compact_archive
    assert scaled["training_archive_limit"] == 256
    assert compact["run_id"] != scaled["run_id"]
