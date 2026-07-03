from __future__ import annotations

import tempfile
from pathlib import Path

from multilevel.exploratory import run_exploratory_search


def test_exploratory_search_smoke_epsilon_net():
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_exploratory_search(
            problem="epsilon_net",
            seed=0,
            iterations=2,
            population_size=4,
            elite_size=2,
            out_dir=Path(tmp) / "epsilon",
            n=5,
            grid=5,
            threshold=2,
            k=1,
        )
    assert summary["problem"] == "epsilon_net"
    assert summary["completed_iterations"] == 2
    assert summary["num_exact_calls"] > 0


def test_exploratory_search_smoke_graph_separation():
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_exploratory_search(
            problem="graph_separation",
            seed=0,
            iterations=1,
            population_size=3,
            elite_size=1,
            out_dir=Path(tmp) / "graph",
            n=4,
            grid=3,
            mixed_grid=2,
            timeout_seconds=1.0,
        )
    assert summary["problem"] == "graph_separation"
    assert summary["completed_iterations"] == 1
    assert summary["num_exact_calls"] > 0
