from __future__ import annotations

import copy
import json
import math
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multilevel.canonical import attach_certificate_hash, sha256_obj, write_json
from multilevel.provenance import dependency_versions, runtime_provenance
from multilevel.random_instances import GENERATORS
from multilevel.render import render_certificate
from multilevel.scorers import epsilon_net, graph_separation


SCORERS = {
    "graph_separation": graph_separation,
    "epsilon_net": epsilon_net,
}


def run_exploratory_search(
    *,
    problem: str,
    seed: int,
    iterations: int,
    population_size: int,
    elite_size: int,
    out_dir: str | Path,
    n: int,
    grid: int,
    run_id: str | None = None,
    budget_seconds: int | None = None,
    mixed_grid: int | None = None,
    timeout_seconds: float | None = None,
    threshold: int | None = None,
    k: int | None = None,
) -> dict[str, Any]:
    if problem not in SCORERS:
        raise ValueError(f"unsupported exploratory problem: {problem}")
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
    exact_timeouts = 0
    invalid = 0
    duplicates = 0
    completed_iterations = 0
    stop_reason = "completed"
    seen: set[str] = set()
    provenance = runtime_provenance(Path.cwd())

    config = {
        "mixed_grid": mixed_grid if mixed_grid is not None else max(2, min(5, grid)),
        "timeout_seconds": timeout_seconds if timeout_seconds is not None else 8.0,
        "threshold": threshold,
        "k": k,
    }
    population = [
        _initial_candidate(problem, rng, n=n, grid=grid, config=config)
        for _ in range(population_size)
    ]

    def budget_exhausted() -> bool:
        return budget_seconds is not None and budget_seconds > 0 and time.perf_counter() - start >= budget_seconds

    def maybe_export(cert: dict[str, Any], generation: int) -> None:
        nonlocal best_cert, best_path, best_rendering_path, time_to_best
        if cert.get("solver_status") == "timeout":
            return
        if best_cert is not None and float(cert["score"]) <= float(best_cert["score"]):
            return
        cert_path = cert_dir / f"best_iter{generation:06d}_{cert['certificate_hash'][:12]}.json"
        rendering_path = render_dir / f"best_iter{generation:06d}_{cert['certificate_hash'][:12]}.svg"
        write_json(cert_path, cert)
        render_certificate(cert, rendering_path)
        best_cert = cert
        best_path = cert_path
        best_rendering_path = rendering_path
        time_to_best = time.perf_counter() - start

    with event_path.open("w", encoding="utf-8") as events:
        for generation in range(iterations):
            if budget_exhausted():
                stop_reason = "budget_exhausted"
                events.write(json.dumps({
                    "schema": "stop_event_v1",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "problem": problem,
                    "reason": stop_reason,
                    "generation": generation,
                    "elapsed_seconds": time.perf_counter() - start,
                    "budget_seconds": budget_seconds,
                }, sort_keys=True) + "\n")
                break
            scored: list[tuple[float, dict[str, Any], dict[str, Any], str]] = []
            for instance in population:
                candidate = _repair_candidate(problem, instance, n=n, grid=grid, config=config)
                candidate_id = sha256_obj(candidate)
                if candidate_id in seen:
                    duplicates += 1
                    continue
                seen.add(candidate_id)
                candidate_start = time.perf_counter()
                try:
                    cert = SCORERS[problem].score_instance(candidate)
                    exact_calls += 1
                    if cert.get("solver_status") == "timeout":
                        exact_timeouts += 1
                    cert["candidate_id"] = candidate_id
                    cert["source_type"] = candidate.get("_source_type", "exploratory_search")
                    cert["generation"] = generation
                    cert = dict(cert)
                    cert.update(provenance)
                    cert = attach_certificate_hash(cert)
                    rank_score, features = _rank_certificate(problem, cert)
                    maybe_export(cert, generation)
                    event = {
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "generation": generation,
                        "candidate_id": candidate_id,
                        "source_type": cert["source_type"],
                        "search_score": rank_score,
                        "surrogate_features": features,
                        "exact_status": cert["solver_status"],
                        "exact_score": cert["score"],
                        "certificate_hash": cert["certificate_hash"],
                        "improved_best": best_cert is cert,
                        "wall_seconds": time.perf_counter() - candidate_start,
                    }
                    scored.append((rank_score, candidate, features, candidate_id))
                except Exception as exc:
                    invalid += 1
                    event = {
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "generation": generation,
                        "candidate_id": candidate_id,
                        "exact_status": "invalid",
                        "error": repr(exc),
                        "wall_seconds": time.perf_counter() - candidate_start,
                    }
                events.write(json.dumps(event, sort_keys=True) + "\n")
            scored.sort(key=lambda item: item[0], reverse=True)
            elites = [instance for _, instance, _, _ in scored[: max(1, elite_size)]]
            next_population = [copy.deepcopy(instance) for instance in elites]
            while len(next_population) < population_size:
                if not elites or rng.random() < 0.15:
                    fresh = _initial_candidate(problem, rng, n=n, grid=grid, config=config)
                    fresh["_source_type"] = "random_reseed"
                    next_population.append(fresh)
                    continue
                child = _mutate_candidate(problem, rng.choice(elites), rng, n=n, grid=grid, config=config)
                child["_source_type"] = "exploratory_mutation"
                next_population.append(child)
            population = next_population[:population_size]
            completed_iterations = generation + 1
        else:
            completed_iterations = iterations

    summary = {
        "schema": "run_summary_v1",
        "run_id": run_id,
        "stage": "exploratory",
        "problem": problem,
        "representation": _representation_name(problem),
        "local_search": _local_search_name(problem),
        "surrogate": _surrogate_name(problem),
        "control_mode": "exploratory_search",
        "rng_seed": seed,
        "iterations": iterations,
        "completed_iterations": completed_iterations,
        "stop_reason": stop_reason,
        "population_size": population_size,
        "elite_size": elite_size,
        "n": n,
        "grid": grid,
        "budget_seconds": budget_seconds,
        "exploratory_hparams": config,
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
        "num_exact_timeouts": exact_timeouts,
        "num_invalid_samples": invalid,
        "num_repaired_samples": 0,
        "num_duplicates": duplicates,
        "num_exports": len(list(cert_dir.glob("*.json"))),
        "event_stream": str(event_path),
        "elapsed_seconds": time.perf_counter() - start,
    }
    write_json(out / "summary.json", summary)
    return summary


def _initial_candidate(problem: str, rng: random.Random, *, n: int, grid: int, config: dict[str, Any]) -> dict[str, Any]:
    instance = GENERATORS[problem](rng, n=n, grid=grid)
    if problem == "graph_separation":
        instance["mixed_grid"] = int(config["mixed_grid"])
        instance["timeout_seconds"] = float(config["timeout_seconds"])
    elif problem == "epsilon_net":
        _set_epsilon_parameters(instance, config=config)
    return instance


def _repair_candidate(problem: str, instance: dict[str, Any], *, n: int, grid: int, config: dict[str, Any]) -> dict[str, Any]:
    if problem == "graph_separation":
        rects = _clean_rectangles(instance.get("rectangles"), n_min=max(3, min(n, 3)), n_max=max(n * 2, n + 4), grid=grid)
        return {
            "schema": "graph_separation_instance_v1",
            "rectangles": rects,
            "mixed_grid": int(config["mixed_grid"]),
            "timeout_seconds": float(config["timeout_seconds"]),
        }
    if problem == "epsilon_net":
        points = _clean_points(instance.get("points"), n_min=max(3, n), n_max=max(3, n), grid=grid)
        clean = {"schema": "epsilon_net_instance_v1", "points": points}
        _set_epsilon_parameters(clean, config=config)
        return clean
    raise ValueError(problem)


def _mutate_candidate(problem: str, instance: dict[str, Any], rng: random.Random, *, n: int, grid: int, config: dict[str, Any]) -> dict[str, Any]:
    child = copy.deepcopy(instance)
    if problem == "graph_separation":
        rects = child.get("rectangles", [])
        move = rng.choice(["move", "resize", "duplicate", "delete", "add", "motif_shift"])
        if move == "delete" and len(rects) > 3:
            del rects[rng.randrange(len(rects))]
        elif move == "add" and len(rects) < max(n * 2, n + 4):
            rects.append(_random_rectangle(rng, grid=grid))
        elif move == "duplicate" and rects and len(rects) < max(n * 2, n + 4):
            r = list(rects[rng.randrange(len(rects))])
            dx, dy = rng.choice([-2, -1, 1, 2]), rng.choice([-2, -1, 1, 2])
            rects.append([r[0] + dx, r[1] + dx, r[2] + dy, r[3] + dy])
        elif move == "motif_shift" and rects:
            x_cut = rng.randrange(0, max(1, grid + 1))
            y_cut = rng.randrange(0, max(1, grid + 1))
            dx, dy = rng.choice([-1, 1]), rng.choice([-1, 1])
            for rect in rects:
                if (rect[0] + rect[1]) // 2 >= x_cut or (rect[2] + rect[3]) // 2 >= y_cut:
                    rect[0] += dx
                    rect[1] += dx
                    rect[2] += dy
                    rect[3] += dy
        elif rects:
            idx = rng.randrange(len(rects))
            x1, x2, y1, y2 = rects[idx]
            if move == "resize":
                x1 += rng.choice([-1, 0])
                x2 += rng.choice([0, 1])
                y1 += rng.choice([-1, 0])
                y2 += rng.choice([0, 1])
            else:
                dx, dy = rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1])
                x1, x2, y1, y2 = x1 + dx, x2 + dx, y1 + dy, y2 + dy
            rects[idx] = [x1, x2, y1, y2]
    elif problem == "epsilon_net":
        points = child.get("points", [])
        move = rng.choice(["move", "add", "delete", "layer", "affine_jitter"])
        if move == "delete" and len(points) > max(3, n - 2):
            del points[rng.randrange(len(points))]
        elif move == "add":
            new_point = [rng.randrange(0, grid + 1), rng.randrange(0, grid + 1)]
            if len(points) < n:
                points.append(new_point)
            elif points:
                points[rng.randrange(len(points))] = new_point
        elif move == "layer" and points:
            layer = rng.choice([0, grid, grid // 2])
            if rng.random() < 0.5:
                points[rng.randrange(len(points))] = [rng.randrange(0, grid + 1), layer]
            else:
                points[rng.randrange(len(points))] = [layer, rng.randrange(0, grid + 1)]
        elif move == "affine_jitter" and points:
            dx, dy = rng.choice([-1, 1]), rng.choice([-1, 1])
            for point in points:
                if rng.random() < 0.5:
                    point[0] += dx
                    point[1] += dy
        elif points:
            idx = rng.randrange(len(points))
            points[idx][0] += rng.choice([-1, 0, 1])
            points[idx][1] += rng.choice([-1, 0, 1])
    return _repair_candidate(problem, child, n=n, grid=grid, config=config)


def _rank_certificate(problem: str, cert: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    score = float(cert.get("score") or 0.0)
    if problem == "graph_separation":
        n = max(1, int(cert.get("n", 1)))
        edges = len(cert.get("rectangle_edges", []))
        density = edges / max(1, n * (n - 1) / 2)
        balance = 1.0 - abs(0.5 - density)
        status_bonus = {
            "bounded_grid_infeasible": 2.0,
            "timeout": 0.25,
            "representable": 0.0,
        }.get(str(cert.get("mixed_status")), 0.0)
        features = {
            "edge_density": density,
            "density_balance": balance,
            "clique_number": cert.get("clique_number"),
            "independence_number": cert.get("independence_number"),
            "mixed_status": cert.get("mixed_status"),
        }
        return score * 10.0 + status_bonus + balance + 0.01 * n, features
    if problem == "epsilon_net":
        total = max(1, int(cert.get("num_k_subsets", 1)))
        witnesses = int(cert.get("num_witness_halfplanes", 0))
        coverage = witnesses / total
        lower = float(cert.get("lower_bound_ratio") or 0.0)
        features = {
            "witness_coverage": coverage,
            "lower_bound_ratio": lower,
            "n": cert.get("n"),
            "threshold": cert.get("threshold"),
            "k": cert.get("k"),
        }
        return score * 10.0 + coverage * lower, features
    raise ValueError(problem)


def _set_epsilon_parameters(instance: dict[str, Any], *, config: dict[str, Any]) -> None:
    n = len(instance.get("points", []))
    threshold = config.get("threshold")
    if threshold is None:
        threshold = max(1, n // 2)
    threshold = max(1, min(int(threshold), n))
    k = config.get("k")
    if k is None:
        k = max(0, threshold - 1)
    k = max(0, min(int(k), n))
    instance["threshold"] = threshold
    instance["k"] = k


def _clean_rectangles(raw: Any, *, n_min: int, n_max: int, grid: int) -> list[list[int]]:
    if not isinstance(raw, list):
        raw = []
    rects = []
    for row in raw[:n_max]:
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            continue
        x1 = _clamp_int(row[0], 0, grid + 1)
        x2 = _clamp_int(row[1], 1, grid + 2)
        y1 = _clamp_int(row[2], 0, grid + 1)
        y2 = _clamp_int(row[3], 1, grid + 2)
        if x2 <= x1:
            x2 = min(grid + 2, x1 + 1)
        if y2 <= y1:
            y2 = min(grid + 2, y1 + 1)
        rects.append([x1, x2, y1, y2])
    while len(rects) < n_min:
        rects.append(_random_rectangle(random.Random(len(rects) + grid), grid=grid))
    return rects


def _clean_points(raw: Any, *, n_min: int, n_max: int, grid: int) -> list[list[int]]:
    if not isinstance(raw, list):
        raw = []
    seen: set[tuple[int, int]] = set()
    points = []
    for row in raw[:n_max]:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        x = _clamp_int(row[0], 0, grid)
        y = _clamp_int(row[1], 0, grid)
        if (x, y) not in seen:
            seen.add((x, y))
            points.append([x, y])
    cursor = 0
    side = max(1, grid + 1)
    while len(points) < n_min:
        x, y = cursor % side, cursor // side
        cursor += 1
        if (x, y) not in seen:
            seen.add((x, y))
            points.append([x, y])
    return points


def _random_rectangle(rng: random.Random, *, grid: int) -> list[int]:
    x1 = rng.randrange(0, grid + 1)
    x2 = rng.randrange(x1 + 1, grid + 3)
    y1 = rng.randrange(0, grid + 1)
    y2 = rng.randrange(y1 + 1, grid + 3)
    return [x1, x2, y1, y2]


def _clamp_int(value: Any, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(round(float(value)))))
    except Exception:
        return low


def _representation_name(problem: str) -> str:
    return {
        "graph_separation": "rectangle_graph_bounded_mixed",
        "epsilon_net": "order_type_points",
    }[problem]


def _local_search_name(problem: str) -> str:
    return {
        "graph_separation": "graph_aware_coordinate_mutation",
        "epsilon_net": "order_type_mutation",
    }[problem]


def _surrogate_name(problem: str) -> str:
    return {
        "graph_separation": "mixed_representation_stress",
        "epsilon_net": "witness_coverage_exact",
    }[problem]
