from __future__ import annotations

import json
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multilevel.canonical import attach_certificate_hash, sha256_obj, write_json
from multilevel.provenance import attach_runtime_provenance, dependency_versions
from multilevel.random_instances import GENERATORS
from multilevel.render import render_certificate
from multilevel.scorers import epsilon_net, graph_separation, guillotine, misr, unit_square


SCORERS = {
    "misr": misr,
    "unit_square": unit_square,
    "guillotine": guillotine,
    "graph_separation": graph_separation,
    "epsilon_net": epsilon_net,
}


def run_random_exact_baseline(
    *,
    problem: str,
    seed: int,
    iterations: int,
    out_dir: str | Path,
    n: int,
    grid: int,
    run_id: str | None = None,
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    if problem not in GENERATORS:
        raise ValueError(f"unknown problem: {problem}")
    out = Path(out_dir)
    cert_dir = out / "certificates"
    render_dir = out / "renderings"
    cert_dir.mkdir(parents=True, exist_ok=True)
    render_dir.mkdir(parents=True, exist_ok=True)
    event_path = out / "events.jsonl"
    rng = random.Random(seed)
    start_iso = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    best_cert: dict[str, Any] | None = None
    best_path: Path | None = None
    best_rendering_path: Path | None = None
    time_to_best: float | None = None
    exact_calls = 0
    failures = 0
    stop_reason = "completed"
    completed_iterations = 0

    def budget_exhausted() -> bool:
        return budget_seconds is not None and budget_seconds > 0 and time.perf_counter() - start >= budget_seconds

    with event_path.open("w", encoding="utf-8") as events:
        for iteration in range(iterations):
            if budget_exhausted():
                stop_reason = "budget_exhausted"
                events.write(json.dumps({
                    "schema": "stop_event_v1",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "problem": problem,
                    "reason": stop_reason,
                    "iteration": iteration,
                    "elapsed_seconds": time.perf_counter() - start,
                    "budget_seconds": budget_seconds,
                }, sort_keys=True) + "\n")
                break
            candidate_start = time.perf_counter()
            instance = GENERATORS[problem](rng, n=n, grid=grid)
            candidate_id = sha256_obj(instance)
            try:
                cert = SCORERS[problem].score_instance(instance)
                exact_calls += 1
                cert["candidate_id"] = candidate_id
                cert["source_type"] = "random_local_only"
                cert["generation"] = iteration
                cert = attach_runtime_provenance(cert, Path.cwd())
                cert = attach_certificate_hash(cert)
                improved = best_cert is None or float(cert["score"]) > float(best_cert["score"])
                if improved:
                    cert_path = cert_dir / f"best_iter{iteration:06d}_{cert['certificate_hash'][:12]}.json"
                    rendering_path = render_dir / f"best_iter{iteration:06d}_{cert['certificate_hash'][:12]}.svg"
                    write_json(cert_path, cert)
                    render_certificate(cert, rendering_path)
                    best_cert = cert
                    best_path = cert_path
                    best_rendering_path = rendering_path
                    time_to_best = time.perf_counter() - start
                event = {
                    "schema": "candidate_event_v1",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "problem": problem,
                    "iteration": iteration,
                    "candidate_id": candidate_id,
                    "score": cert["score"],
                    "certificate_hash": cert["certificate_hash"],
                    "certificate_path": str(best_path) if improved else None,
                    "rendering_path": str(best_rendering_path) if improved else None,
                    "exact_status": cert["solver_status"],
                    "exact_runtime_seconds": cert["exact_runtime_seconds"],
                    "improved_best": improved,
                    "wall_seconds": time.perf_counter() - candidate_start,
                }
            except Exception as exc:  # Keep baseline runs auditable after bad samples.
                failures += 1
                event = {
                    "schema": "candidate_event_v1",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "problem": problem,
                    "iteration": iteration,
                    "candidate_id": candidate_id,
                    "exact_status": "invalid",
                    "error": repr(exc),
                    "improved_best": False,
                    "wall_seconds": time.perf_counter() - candidate_start,
                }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            completed_iterations = iteration + 1
        else:
            completed_iterations = iterations

    summary = {
        "schema": "run_summary_v1",
        "run_id": run_id,
        "stage": "control",
        "problem": problem,
        "representation": {
            "misr": "rect_direct",
            "unit_square": "square_direct",
            "guillotine": "rect_direct_disjoint",
            "graph_separation": "rectangle_graph_bounded_mixed",
            "epsilon_net": "order_type_points",
        }[problem],
        "local_search": "random_local_only",
        "surrogate": "none_exact_all",
        "control_mode": "local_only",
        "rng_seed": seed,
        "iterations": iterations,
        "completed_iterations": completed_iterations,
        "stop_reason": stop_reason,
        "n": n,
        "grid": grid,
        "budget_seconds": budget_seconds,
        "start_time": start_iso,
        "end_time": datetime.now(timezone.utc).isoformat(),
        "return_code": 0,
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "solver_versions": dependency_versions(),
        "best_exact_score": None if best_cert is None else best_cert["score"],
        "time_to_best": time_to_best,
        "best_certificate_path": None if best_path is None else str(best_path),
        "best_rendering_path": None if best_rendering_path is None else str(best_rendering_path),
        "best_certificate_hash": None if best_cert is None else best_cert["certificate_hash"],
        "num_exact_calls": exact_calls,
        "num_exact_timeouts": 0,
        "num_invalid_samples": failures,
        "num_repaired_samples": 0,
        "num_duplicates": 0,
        "num_exports": len(list(cert_dir.glob("*.json"))),
        "event_stream": str(event_path),
        "elapsed_seconds": time.perf_counter() - start,
    }
    write_json(out / "summary.json", summary)
    return summary
