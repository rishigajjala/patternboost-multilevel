from __future__ import annotations

import pytest

from multilevel.scorers import epsilon_net, graph_separation, guillotine, misr, unit_square


def test_misr_smoke():
    cert = misr.score_instance(
        {
            "rectangles": [
                [0, 3, 0, 1],
                [0, 3, 2, 3],
                [1, 2, -1, 4],
                [4, 5, 0, 1],
            ]
        }
    )
    assert cert["solver_status"] == "optimal"
    assert cert["alpha_int"] >= 1
    assert misr.verify_certificate(cert)


def test_misr_triangle_free_constraint_rejects_triangle():
    with pytest.raises(ValueError, match="triangle-free constraint"):
        misr.score_instance(
            {
                "rectangles": [
                    [0, 2, 0, 2],
                    [1, 3, 1, 3],
                    [0, 3, 0, 3],
                ],
                "constraints": {"triangle_free": True},
            }
        )


def test_unit_square_smoke():
    cert = unit_square.score_instance({"squares": [[0, 0], [1, 0], [0, 1], [2, 2]]})
    assert cert["solver_status"] == "optimal"
    assert cert["tau_int"] >= 1
    assert unit_square.verify_certificate(cert)


def test_unit_square_side_length_is_preserved_in_certificate():
    cert = unit_square.score_instance({"squares": [[0, 0], [2, 1], [3, 4], [5, 2]], "side": 2})
    assert cert["solver_status"] == "optimal"
    assert cert["side"] == 2
    assert cert["tau_int"] >= 1
    assert cert["tau_lp"] > 0
    assert unit_square.verify_certificate(cert)


def test_guillotine_smoke():
    cert = guillotine.score_instance(
        {"rectangles": [[0, 2, 0, 1], [3, 5, 0, 1], [1, 4, 2, 3]]}
    )
    assert cert["solver_status"] == "optimal"
    assert cert["saved"] >= 1
    assert cert["threshold_k"] == 2
    assert cert["threshold_exact"] is True
    assert guillotine.verify_certificate(cert)


def test_epsilon_net_smoke():
    cert = epsilon_net.score_instance({"points": [[0, 0], [1, 0], [0, 1]], "threshold": 2, "k": 1})
    assert cert["solver_status"] == "optimal"
    assert cert["all_k_subsets_fail"] is True
    assert epsilon_net.verify_certificate(cert)


def test_graph_separation_smoke():
    cert = graph_separation.score_instance(
        {
            "rectangles": [[0, 2, 0, 2], [1, 3, 1, 3], [4, 5, 4, 5]],
            "mixed_grid": 3,
            "timeout_seconds": 5.0,
        }
    )
    assert cert["solver_status"] in {"representable", "bounded_grid_infeasible"}
    assert graph_separation.verify_certificate(cert)
