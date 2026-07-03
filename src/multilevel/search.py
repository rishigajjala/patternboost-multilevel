from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multilevel.canonical import attach_certificate_hash, sha256_obj, write_json
from multilevel.mutations import mutate_instance
from multilevel.provenance import attach_runtime_provenance
from multilevel.representations import (
    decoded_geometry,
    initial_instance_for_representation,
    repair_instance_for_representation,
)
from multilevel.render import render_certificate
from multilevel.scorers import guillotine, misr, unit_square
from multilevel.surrogates import surrogate_score


SCORERS = {
    "misr": misr,
    "unit_square": unit_square,
    "guillotine": guillotine,
}


def run_component_search(
    *,
    problem: str,
    representation: str,
    local_search: str,
    surrogate: str,
    seed: int,
    iterations: int,
    population_size: int,
    elite_size: int,
    exact_every: int,
    out_dir: str | Path,
    n: int,
    grid: int,
    run_id: str | None = None,
    stage: str = "pilot",
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    cert_dir = out / "certificates"
    render_dir = out / "renderings"
    cert_dir.mkdir(parents=True, exist_ok=True)
    render_dir.mkdir(parents=True, exist_ok=True)
    event_path = out / "events.jsonl"
    rng = random.Random(seed)
    start_iso = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    population = [
        initial_instance_for_representation(problem, representation, rng, n=n, grid=grid)
        for _ in range(population_size)
    ]
    seen: set[str] = set()
    best_cert: dict[str, Any] | None = None
    best_path: Path | None = None
    best_rendering_path: Path | None = None
    time_to_best: float | None = None
    exact_calls = 0
    invalid = 0
    repaired = 0
    duplicates = 0
    stop_reason = "completed"
    completed_iterations = 0

    def budget_exhausted() -> bool:
        return budget_seconds is not None and budget_seconds > 0 and time.perf_counter() - start >= budget_seconds

    def exact_audit(instance: dict[str, Any], generation: int, source: str) -> dict[str, Any] | None:
        nonlocal best_cert, best_path, best_rendering_path, time_to_best, exact_calls
        clean_instance = decoded_geometry(instance)
        try:
            cert = SCORERS[problem].score_instance(clean_instance)
        except Exception:
            return None
        exact_calls += 1
        cert["candidate_id"] = sha256_obj(clean_instance)
        cert["representation"] = representation
        cert["local_search"] = local_search
        cert["surrogate"] = surrogate
        cert["source_type"] = source
        cert["generation"] = generation
        cert = attach_runtime_provenance(cert, Path.cwd())
        cert = attach_certificate_hash(cert)
        if best_cert is None or float(cert["score"]) > float(best_cert["score"]):
            cert_path = cert_dir / f"best_iter{generation:06d}_{cert['certificate_hash'][:12]}.json"
            rendering_path = render_dir / f"best_iter{generation:06d}_{cert['certificate_hash'][:12]}.svg"
            write_json(cert_path, cert)
            render_certificate(cert, rendering_path)
            best_cert = cert
            best_path = cert_path
            best_rendering_path = rendering_path
            time_to_best = time.perf_counter() - start
        return cert

    with event_path.open("w", encoding="utf-8") as events:
        for generation in range(iterations):
            if budget_exhausted():
                stop_reason = "budget_exhausted"
                events.write(json.dumps({
                    "schema": "stop_event_v1",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "reason": stop_reason,
                    "generation": generation,
                    "elapsed_seconds": time.perf_counter() - start,
                    "budget_seconds": budget_seconds,
                }, sort_keys=True) + "\n")
                break
            scored = []
            for instance in population:
                try:
                    before_geometry = decoded_geometry(instance)
                    candidate = repair_instance_for_representation(
                        problem,
                        representation,
                        instance,
                        grid=grid,
                        n_min=2,
                        n_max=max(n * 3, 16),
                    )
                except Exception as exc:
                    invalid += 1
                    events.write(json.dumps({
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "generation": generation,
                        "candidate_id": None,
                        "exact_status": "invalid",
                        "error": repr(exc),
                    }, sort_keys=True) + "\n")
                    continue
                if decoded_geometry(candidate) != before_geometry:
                    repaired += 1
                clean_instance = decoded_geometry(candidate)
                key = sha256_obj(clean_instance)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                try:
                    row = surrogate_score(problem, surrogate, clean_instance)
                except Exception as exc:
                    invalid += 1
                    events.write(json.dumps({
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "generation": generation,
                        "candidate_id": key,
                        "exact_status": "invalid",
                        "error": repr(exc),
                    }, sort_keys=True) + "\n")
                    continue
                scored.append((float(row["surrogate_score"]), candidate, row["features"], key))
            scored.sort(key=lambda item: item[0], reverse=True)
            elites = scored[: max(1, elite_size)]
            if generation % max(1, exact_every) == 0 or generation == iterations - 1:
                for rank, (s_score, instance, features, key) in enumerate(elites):
                    cert = exact_audit(instance, generation, "component_search")
                    events.write(json.dumps({
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "representation": representation,
                        "local_search": local_search,
                        "surrogate": surrogate,
                        "generation": generation,
                        "rank": rank,
                        "candidate_id": key,
                        "surrogate_score": s_score,
                        "surrogate_features": features,
                        "exact_status": None if cert is None else cert["solver_status"],
                        "exact_score": None if cert is None else cert["score"],
                        "best_exact_score": None if best_cert is None else best_cert["score"],
                    }, sort_keys=True) + "\n")
            next_population = [instance for _, instance, _, _ in elites]
            while len(next_population) < population_size:
                if not next_population:
                    next_population.append(
                        initial_instance_for_representation(problem, representation, rng, n=n, grid=grid)
                    )
                    continue
                parent = rng.choice(next_population)
                try:
                    child = mutate_instance(
                        problem,
                        local_search,
                        parent,
                        rng,
                        grid=grid,
                        n_max=max(n * 3, 16),
                        representation=representation,
                    )
                except Exception:
                    invalid += 1
                    child = initial_instance_for_representation(problem, representation, rng, n=n, grid=grid)
                next_population.append(child)
            population = next_population[:population_size]
            completed_iterations = generation + 1
        else:
            completed_iterations = iterations

    summary = {
        "schema": "run_summary_v1",
        "run_id": run_id,
        "stage": stage,
        "problem": problem,
        "representation": representation,
        "local_search": local_search,
        "surrogate": surrogate,
        "control_mode": "component_search",
        "rng_seed": seed,
        "iterations": iterations,
        "completed_iterations": completed_iterations,
        "stop_reason": stop_reason,
        "population_size": population_size,
        "elite_size": elite_size,
        "exact_every": exact_every,
        "n": n,
        "grid": grid,
        "budget_seconds": budget_seconds,
        "start_time": start_iso,
        "end_time": datetime.now(timezone.utc).isoformat(),
        "return_code": 0,
        "best_exact_score": None if best_cert is None else best_cert["score"],
        "time_to_best": time_to_best,
        "best_certificate_path": None if best_path is None else str(best_path),
        "best_rendering_path": None if best_rendering_path is None else str(best_rendering_path),
        "best_certificate_hash": None if best_cert is None else best_cert["certificate_hash"],
        "num_exact_calls": exact_calls,
        "num_exact_timeouts": 0,
        "num_invalid_samples": invalid,
        "num_repaired_samples": repaired,
        "num_duplicates": duplicates,
        "num_exports": len(list(cert_dir.glob("*.json"))),
        "event_stream": str(event_path),
        "elapsed_seconds": time.perf_counter() - start,
    }
    write_json(out / "summary.json", summary)
    return summary
