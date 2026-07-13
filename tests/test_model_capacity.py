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
    assert all(row["elite"] == 6 for row in rows)
    assert all(row["model_samples"] == 16 for row in rows)
    assert all(row["preserve_resolution_diversity"] is False for row in rows)

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
    assert compact["training_archive_limit"] == 48
    assert scaled["training_archive_limit"] == 256
    assert compact["run_id"] != scaled["run_id"]
