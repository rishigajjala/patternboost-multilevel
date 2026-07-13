from __future__ import annotations

import copy
import itertools
import math
import random
from typing import Any

from multilevel import misr_sequences
from multilevel.components import LARGE_EXAMPLE_CONSTRAINTS
from multilevel.random_instances import GENERATORS
from multilevel.scorers import guillotine as guillotine_scorer
from multilevel.scorers import misr as misr_scorer
from multilevel.scorers import unit_square as unit_square_scorer
from multilevel.representations import (
    _can_add_triangle_free,
    _guillotine_canonicalize,
    _guillotine_dynamic_side,
    _guillotine_obstruction_rectangles,
    _guillotine_random_rect,
    _normalize_square_coordinates,
    _quadratic_program_payload,
    _rectangles_from_quadratic_program_payload,
    _triangle_free_candidate_pool,
    _triangle_free_key,
    default_representation,
    repair_instance_for_representation,
)


SYMMETRY_CROSSOVER_LOCAL_SEARCH = "symmetry_crossover_hillclimb"
SYMMETRY_CROSSOVER_STEPS = 25
DIVERSE_ANNEALED_LOCAL_SEARCH = "diverse_annealed_crossover"
DIVERSE_ANNEALED_STEPS = 32


def mutate_instance(
    problem: str,
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int = 2,
    n_max: int = 64,
    representation: str | None = None,
    mate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rep = representation or str(instance.get("_representation") or default_representation(problem))
    if local_search == DIVERSE_ANNEALED_LOCAL_SEARCH:
        if problem != "unit_square":
            raise ValueError(f"{DIVERSE_ANNEALED_LOCAL_SEARCH} only supports unit_square")
        return _diverse_annealed_square_search(
            instance,
            mate,
            rng,
            grid=grid,
            n_min=n_min,
            n_max=n_max,
            representation=rep,
        )
    if local_search == SYMMETRY_CROSSOVER_LOCAL_SEARCH:
        return _symmetry_crossover_hillclimb(
            problem,
            instance,
            rng,
            grid=grid,
            n_min=n_min,
            n_max=n_max,
            representation=rep,
        )
    if problem == "misr":
        child = mutate_misr(local_search, instance, rng, grid=grid, n_min=n_min, n_max=n_max, representation=rep)
        return repair_instance_for_representation(problem, rep, child, grid=grid, n_min=n_min, n_max=n_max)
    if problem == "unit_square":
        child = mutate_unit_square(local_search, instance, rng, grid=grid, n_min=n_min, n_max=n_max, representation=rep)
        return repair_instance_for_representation(problem, rep, child, grid=grid, n_min=n_min, n_max=n_max)
    if problem == "guillotine":
        child = mutate_guillotine(local_search, instance, rng, grid=grid, n_min=n_min, n_max=n_max, representation=rep)
        return repair_instance_for_representation(problem, rep, child, grid=grid, n_min=n_min, n_max=n_max)
    raise ValueError(f"unknown problem: {problem}")


def _symmetry_crossover_hillclimb(
    problem: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
    representation: str,
) -> dict[str, Any]:
    """Run the imported 55/25/10/10 move portfolio with exact acceptance."""
    best = repair_instance_for_representation(
        problem,
        representation,
        copy.deepcopy(instance),
        grid=grid,
        n_min=n_min,
        n_max=n_max,
    )
    best_key = _exact_hillclimb_key(problem, best)
    accepted = 0
    for _ in range(SYMMETRY_CROSSOVER_STEPS):
        if problem == "misr" and representation == "quadratic_program_rectangles":
            trial = _mutate_quadratic_program_portfolio(best, rng, grid=grid, n_min=n_min, n_max=n_max)
        else:
            trial = _mutate_geometry_portfolio(problem, best, rng, grid=grid)
            trial.pop("_representation_payload", None)
        try:
            trial = repair_instance_for_representation(
                problem,
                representation,
                trial,
                grid=grid,
                n_min=n_min,
                n_max=n_max,
            )
            trial_key = _exact_hillclimb_key(problem, trial)
        except Exception:
            continue
        if trial_key >= best_key:
            best = trial
            best_key = trial_key
            accepted += 1
    best["_local_search_payload"] = {
        "algorithm": SYMMETRY_CROSSOVER_LOCAL_SEARCH,
        "steps": SYMMETRY_CROSSOVER_STEPS,
        "accepted": accepted,
        "move_probabilities": {"shift": 0.55, "random_move": 0.25, "crossover": 0.10, "symmetry": 0.10},
        "acceptance": "exact_nonworsening",
    }
    return best


def _diverse_annealed_square_search(
    instance: dict[str, Any],
    mate: dict[str, Any] | None,
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
    representation: str,
) -> dict[str, Any]:
    """Explore beyond a local optimum without encoding a desired construction."""
    parent = repair_instance_for_representation(
        "unit_square",
        representation,
        copy.deepcopy(instance),
        grid=grid,
        n_min=n_min,
        n_max=n_max,
    )
    parent_cert = unit_square_scorer.score_instance(decoded_square_geometry(parent))
    current = parent
    current_cert = parent_cert
    best = parent
    best_cert = parent_cert
    mate_used = False

    if mate is not None and int(mate.get("side", 1)) == int(parent.get("side", 1)):
        try:
            recombined = _recombine_unit_square_parents(parent, mate, rng, grid=grid)
            recombined = repair_instance_for_representation(
                "unit_square",
                representation,
                recombined,
                grid=grid,
                n_min=n_min,
                n_max=n_max,
            )
            recombined_cert = unit_square_scorer.score_instance(decoded_square_geometry(recombined))
            current = recombined
            current_cert = recombined_cert
            mate_used = True
            if _unit_square_escape_key(recombined_cert) > _unit_square_escape_key(best_cert):
                best = recombined
                best_cert = recombined_cert
        except Exception:
            pass

    accepted = 0
    accepted_downhill = 0
    for step in range(DIVERSE_ANNEALED_STEPS):
        trial = _compound_unit_square_trial(current, rng, grid=grid)
        try:
            trial = repair_instance_for_representation(
                "unit_square",
                representation,
                trial,
                grid=grid,
                n_min=n_min,
                n_max=n_max,
            )
            trial_cert = unit_square_scorer.score_instance(decoded_square_geometry(trial))
        except Exception:
            continue

        progress = step / max(1, DIVERSE_ANNEALED_STEPS - 1)
        temperature = 0.05 * (1.0 - progress) + 0.005
        delta = _unit_square_escape_energy(trial_cert) - _unit_square_escape_energy(current_cert)
        accept = delta >= 0.0 or rng.random() < math.exp(max(-50.0, delta / temperature))
        if accept:
            current = trial
            current_cert = trial_cert
            accepted += 1
            if delta < 0.0:
                accepted_downhill += 1
        if _unit_square_escape_key(trial_cert) > _unit_square_escape_key(best_cert):
            best = trial
            best_cert = trial_cert

    best["_local_search_payload"] = {
        "algorithm": DIVERSE_ANNEALED_LOCAL_SEARCH,
        "steps": DIVERSE_ANNEALED_STEPS,
        "accepted": accepted,
        "accepted_downhill": accepted_downhill,
        "mate_used": mate_used,
        "compound_moves": [2, 3, 4, 5],
        "acceptance": "exact_simulated_annealing_with_best_retention",
        "temperature": {"initial": 0.055, "final": 0.005},
        "move_probabilities": {
            "shift": 0.35,
            "random_move": 0.20,
            "coordinate_swap": 0.15,
            "line_align": 0.20,
            "cluster_shift": 0.10,
        },
    }
    return best


def decoded_square_geometry(instance: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "unit_square_instance_v1",
        "squares": copy.deepcopy(instance.get("squares", [])),
        "side": instance.get("side", 1),
    }


def _unit_square_escape_key(cert: dict[str, Any]) -> tuple[float, float, int, int, float, float]:
    tau_int = float(cert.get("tau_int", 0.0))
    min_tau = float(LARGE_EXAMPLE_CONSTRAINTS["unit_square"]["min_tau_int"])
    return (
        float(tau_int >= min_tau),
        float(cert.get("score", 0.0)),
        len(cert.get("lp_primal") or {}),
        int(cert.get("line_count", 0)),
        tau_int,
        -float(cert.get("tau_lp", 0.0)),
    )


def _unit_square_escape_energy(cert: dict[str, Any]) -> float:
    tau_int = float(cert.get("tau_int", 0.0))
    min_tau = float(LARGE_EXAMPLE_CONSTRAINTS["unit_square"]["min_tau_int"])
    admissibility = min(1.0, tau_int / max(1.0, min_tau))
    return float(cert.get("score", 0.0)) + 0.20 * admissibility


def _recombine_unit_square_parents(
    first: dict[str, Any],
    second: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
) -> dict[str, Any]:
    child = copy.deepcopy(first)
    first_squares = [list(row) for row in first.get("squares", [])]
    second_squares = [list(row) for row in second.get("squares", [])]
    if not first_squares or not second_squares:
        return child
    target = len(first_squares)

    candidates: list[list[int]] = []
    if rng.random() < 0.5:
        first_order = rng.sample(first_squares, len(first_squares))
        second_order = rng.sample(second_squares, len(second_squares))
        cut = rng.randrange(1, target) if target > 1 else 1
        candidates.extend(first_order[:cut])
        candidates.extend(second_order[: max(0, target - cut)])
    else:
        xs = [int(row[0]) for row in first_squares]
        ys = [int(row[1]) for row in second_squares]
        rng.shuffle(xs)
        rng.shuffle(ys)
        candidates.extend([[xs[index % len(xs)], ys[index % len(ys)]] for index in range(target)])

    unique: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    for x, y in [*candidates, *first_squares, *second_squares]:
        point = (max(0, min(grid, int(x))), max(0, min(grid, int(y))))
        if point in seen:
            continue
        seen.add(point)
        unique.append([point[0], point[1]])
        if len(unique) >= target:
            break
    while len(unique) < target:
        point = (rng.randrange(grid + 1), rng.randrange(grid + 1))
        if point in seen:
            continue
        seen.add(point)
        unique.append([point[0], point[1]])
    child["squares"] = unique
    child.pop("_local_search_payload", None)
    return child


def _compound_unit_square_trial(
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
) -> dict[str, Any]:
    trial = copy.deepcopy(instance)
    move_count = rng.choices((2, 3, 4, 5), weights=(4, 4, 2, 1), k=1)[0]
    for _ in range(move_count):
        _unit_square_escape_primitive(trial, rng, grid=grid)
    trial.pop("_local_search_payload", None)
    trial.pop("_representation_payload", None)
    return trial


def _unit_square_escape_primitive(instance: dict[str, Any], rng: random.Random, *, grid: int) -> None:
    squares = instance.get("squares", [])
    if not squares:
        return
    draw = rng.random()
    if draw < 0.35:
        index = rng.randrange(len(squares))
        radius = rng.choice((1, 1, 1, 2))
        dx = rng.randrange(-radius, radius + 1)
        dy = rng.randrange(-radius, radius + 1)
        if dx == 0 and dy == 0:
            dx = rng.choice((-1, 1))
        squares[index] = [
            max(0, min(grid, int(squares[index][0]) + dx)),
            max(0, min(grid, int(squares[index][1]) + dy)),
        ]
    elif draw < 0.55:
        squares[rng.randrange(len(squares))] = [rng.randrange(grid + 1), rng.randrange(grid + 1)]
    elif draw < 0.70 and len(squares) >= 2:
        first, second = rng.sample(range(len(squares)), 2)
        if rng.random() < 0.5:
            squares[first][0], squares[second][0] = squares[second][0], squares[first][0]
        else:
            squares[first][1], squares[second][1] = squares[second][1], squares[first][1]
    elif draw < 0.90 and len(squares) >= 2:
        index, reference = rng.sample(range(len(squares)), 2)
        side = max(1, int(instance.get("side", 1) or 1))
        if rng.random() < 0.5:
            squares[index][0] = max(0, min(grid, int(squares[reference][0]) + rng.choice((-side, 0, side))))
        else:
            squares[index][1] = max(0, min(grid, int(squares[reference][1]) + rng.choice((-side, 0, side))))
    else:
        count = rng.randrange(2, min(6, len(squares)) + 1) if len(squares) >= 2 else 1
        selected = rng.sample(range(len(squares)), count)
        dx, dy = rng.choice((-2, -1, 0, 1, 2)), rng.choice((-2, -1, 0, 1, 2))
        if dx == 0 and dy == 0:
            dx = rng.choice((-1, 1))
        for index in selected:
            squares[index] = [
                max(0, min(grid, int(squares[index][0]) + dx)),
                max(0, min(grid, int(squares[index][1]) + dy)),
            ]


def _exact_hillclimb_key(problem: str, instance: dict[str, Any]) -> tuple[float, float, float, float]:
    geometry = {key: value for key, value in instance.items() if not key.startswith("_")}
    scorer = {
        "misr": misr_scorer,
        "unit_square": unit_square_scorer,
        "guillotine": guillotine_scorer,
    }[problem]
    cert = scorer.score_instance(geometry)
    score = float(cert["score"])
    if problem == "misr":
        return (1.0, score, float(cert.get("alpha_lp", 0.0)), -float(cert.get("alpha_int", 0.0)))
    if problem == "unit_square":
        tau_int = float(cert.get("tau_int", 0.0))
        min_tau = float(LARGE_EXAMPLE_CONSTRAINTS[problem]["min_tau_int"])
        return (float(tau_int >= min_tau), score, tau_int, -float(cert.get("tau_lp", 0.0)))
    destroyed = float(cert.get("destroyed", 0.0))
    min_destroyed = float(LARGE_EXAMPLE_CONSTRAINTS[problem]["min_destroyed"])
    return (float(destroyed >= min_destroyed), score, destroyed, -float(cert.get("saved", 0.0)))


def _portfolio_move(rng: random.Random) -> str:
    draw = rng.random()
    if draw < 0.55:
        return "shift"
    if draw < 0.80:
        return "random_move"
    if draw < 0.90:
        return "crossover"
    return "symmetry"


def _mutate_geometry_portfolio(
    problem: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
) -> dict[str, Any]:
    trial = copy.deepcopy(instance)
    move = _portfolio_move(rng)
    if problem == "unit_square":
        squares = trial.get("squares", [])
        if not squares:
            return trial
        if move == "shift":
            idx = rng.randrange(len(squares))
            dx, dy = rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1])
            if dx == 0 and dy == 0:
                dx = rng.choice([-1, 1])
            squares[idx] = [max(0, min(grid, squares[idx][0] + dx)), max(0, min(grid, squares[idx][1] + dy))]
        elif move == "random_move":
            squares[rng.randrange(len(squares))] = [rng.randrange(grid + 1), rng.randrange(grid + 1)]
        elif move == "crossover" and len(squares) >= 2:
            first, second = rng.sample(range(len(squares)), 2)
            x1, y1 = squares[first]
            x2, y2 = squares[second]
            squares[first], squares[second] = [x1, y2], [x2, y1]
        else:
            trial["squares"] = _random_d4_squares(squares, rng)
        return trial

    rectangles = trial.get("rectangles", [])
    if not rectangles:
        return trial
    side = max(grid + 2, max((max(rect) for rect in rectangles), default=grid + 2))
    if move == "shift":
        idx = rng.randrange(len(rectangles))
        dx, dy = rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1])
        if dx == 0 and dy == 0:
            dx = rng.choice([-1, 1])
        x1, x2, y1, y2 = rectangles[idx]
        width, height = x2 - x1, y2 - y1
        nx = max(0, min(max(0, side - width), x1 + dx))
        ny = max(0, min(max(0, side - height), y1 + dy))
        rectangles[idx] = [nx, nx + width, ny, ny + height]
    elif move == "random_move":
        idx = rng.randrange(len(rectangles))
        x1, x2, y1, y2 = rectangles[idx]
        width, height = x2 - x1, y2 - y1
        nx = rng.randrange(max(1, side - width + 1))
        ny = rng.randrange(max(1, side - height + 1))
        rectangles[idx] = [nx, nx + width, ny, ny + height]
    elif move == "crossover" and len(rectangles) >= 2:
        first, second = rng.sample(range(len(rectangles)), 2)
        a, b = rectangles[first], rectangles[second]
        rectangles[first] = [a[0], a[1], b[2], b[3]]
        rectangles[second] = [b[0], b[1], a[2], a[3]]
    else:
        trial["rectangles"] = _random_d4_rectangles(rectangles, rng)
    return trial


def _random_d4_squares(squares: list[list[int]], rng: random.Random) -> list[list[int]]:
    swap_axes = bool(rng.randrange(2))
    x_sign = rng.choice([-1, 1])
    y_sign = rng.choice([-1, 1])
    transformed = []
    for x, y in squares:
        a, b = (y, x) if swap_axes else (x, y)
        transformed.append([x_sign * a, y_sign * b])
    min_x = min(x for x, _ in transformed)
    min_y = min(y for _, y in transformed)
    return sorted([[x - min_x, y - min_y] for x, y in transformed])


def _random_d4_rectangles(rectangles: list[list[int]], rng: random.Random) -> list[list[int]]:
    swap_axes = bool(rng.randrange(2))
    x_sign = rng.choice([-1, 1])
    y_sign = rng.choice([-1, 1])
    transformed = []
    for x1, x2, y1, y2 in rectangles:
        x_interval = (y1, y2) if swap_axes else (x1, x2)
        y_interval = (x1, x2) if swap_axes else (y1, y2)
        tx1, tx2 = x_interval if x_sign > 0 else (-x_interval[1], -x_interval[0])
        ty1, ty2 = y_interval if y_sign > 0 else (-y_interval[1], -y_interval[0])
        transformed.append([tx1, tx2, ty1, ty2])
    min_x = min(rect[0] for rect in transformed)
    min_y = min(rect[2] for rect in transformed)
    return sorted([[x1 - min_x, x2 - min_x, y1 - min_y, y2 - min_y] for x1, x2, y1, y2 in transformed])


def _mutate_quadratic_program_portfolio(
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    target_n = max(n_min, min(n_max, len(instance.get("rectangles", [])) or n_min))
    payload = _quadratic_program_payload(instance.get("_representation_payload", {}), n=target_n, grid=grid)
    coeffs = payload["coeffs"]
    move = _portfolio_move(rng)
    if move in {"shift", "random_move"}:
        name = rng.choice(tuple(coeffs))
        values = coeffs[name]
        idx = rng.randrange(len(values))
        bound = int(payload["coeff_bound"])
        if move == "shift":
            values[idx] = max(-bound, min(bound, values[idx] + rng.choice([-1, 1])))
        else:
            values[idx] = rng.randrange(-bound, bound + 1)
    elif move == "crossover":
        first_name, second_name = rng.sample(tuple(coeffs), 2)
        first, second = coeffs[first_name], coeffs[second_name]
        idx = rng.randrange(min(len(first), len(second)))
        first[idx], second[idx] = second[idx], first[idx]
    else:
        coeffs["a"], coeffs["c"] = coeffs["c"], coeffs["a"]
        coeffs["b"], coeffs["d"] = coeffs["d"], coeffs["b"]
    return {
        "schema": "misr_instance_v1",
        "rectangles": _rectangles_from_quadratic_program_payload(payload, grid=grid),
        "constraints": {"triangle_free": True},
        "_representation": "quadratic_program_rectangles",
        "_representation_payload": payload,
    }


def mutate_misr(
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
    representation: str | None = None,
) -> dict[str, Any]:
    if representation == "endpoint_sequence_pair":
        return mutate_misr_endpoint_sequence_pair(
            local_search,
            instance,
            rng,
            n_min=n_min,
            n_max=n_max,
        )
    if representation == "quadratic_program_rectangles":
        return mutate_misr_quadratic_program(
            local_search,
            instance,
            rng,
            grid=grid,
            n_min=n_min,
            n_max=n_max,
        )
    if representation == "triangle_free_rect":
        return mutate_misr_triangle_free_rectangles(
            local_search,
            instance,
            rng,
            grid=grid,
            n_min=n_min,
            n_max=n_max,
        )
    child = copy.deepcopy(instance)
    rects = child["rectangles"]
    moves = ["jitter", "resize", "duplicate", "delete"]
    if local_search == "lp_dual_pivot":
        moves += ["duplicate", "resize", "align_edge"]
    elif local_search == "motif_blowup":
        moves += ["duplicate", "duplicate", "motif_copy"]
    if representation == "graph_realized":
        moves += ["cluster_jitter"]
    elif representation == "clique_layer_grammar":
        moves += ["layer_shift"]
    move = rng.choice(moves)
    if move == "delete" and len(rects) > n_min:
        del rects[rng.randrange(len(rects))]
    elif move == "duplicate" and len(rects) < n_max and rects:
        r = list(rects[rng.randrange(len(rects))])
        dx, dy = rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1])
        rects.append([max(0, r[0] + dx), max(1, r[1] + dx), max(0, r[2] + dy), max(1, r[3] + dy)])
    elif move == "motif_copy" and len(rects) < n_max and rects:
        anchor = rng.randrange(len(rects))
        motif = rects[max(0, anchor - 1) : min(len(rects), anchor + 2)]
        dx = rng.choice([-3, -2, 2, 3])
        dy = rng.choice([-3, -2, 2, 3])
        for r in motif[: max(1, n_max - len(rects))]:
            rects.append([r[0] + dx, r[1] + dx, r[2] + dy, r[3] + dy])
    elif move == "align_edge" and len(rects) >= 2:
        idx = rng.randrange(len(rects))
        ref = rects[rng.randrange(len(rects))]
        while ref is rects[idx] and len(rects) > 1:
            ref = rects[rng.randrange(len(rects))]
        x1, x2, y1, y2 = rects[idx]
        edge = rng.choice(["left", "right", "bottom", "top"])
        if edge == "left":
            x1 = ref[0]
        elif edge == "right":
            x2 = ref[1]
        elif edge == "bottom":
            y1 = ref[2]
        else:
            y2 = ref[3]
        rects[idx] = [x1, x2, y1, y2]
    elif move == "cluster_jitter" and rects:
        payload = child.get("_representation_payload", {})
        skeleton = payload.get("skeleton", []) if isinstance(payload, dict) else []
        clusters = sorted({row.get("cluster") for row in skeleton if isinstance(row, dict) and "cluster" in row})
        cluster = rng.choice(clusters) if clusters else None
        dx, dy = rng.choice([-1, 1]), rng.choice([-1, 1])
        for idx, rect in enumerate(rects):
            skel_cluster = skeleton[idx].get("cluster") if idx < len(skeleton) and isinstance(skeleton[idx], dict) else None
            if cluster is None or skel_cluster == cluster:
                rects[idx] = [rect[0] + dx, rect[1] + dx, rect[2] + dy, rect[3] + dy]
    elif move == "layer_shift" and rects:
        payload = child.get("_representation_payload", {})
        assignments = payload.get("assignments", []) if isinstance(payload, dict) else []
        layers = sorted({row.get("layer") for row in assignments if isinstance(row, dict) and "layer" in row})
        layer = rng.choice(layers) if layers else rng.randrange(max(1, min(4, len(rects))))
        dy = rng.choice([-1, 1])
        for idx, rect in enumerate(rects):
            assigned = assignments[idx].get("layer") if idx < len(assignments) and isinstance(assignments[idx], dict) else idx % max(1, len(layers) or 1)
            if assigned == layer:
                rects[idx] = [rect[0], rect[1], rect[2] + dy, rect[3] + dy]
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
        x1 = max(0, min(grid, x1))
        x2 = max(x1 + 1, min(grid + 2, x2))
        y1 = max(0, min(grid, y1))
        y2 = max(y1 + 1, min(grid + 2, y2))
        rects[idx] = [x1, x2, y1, y2]
    return child


def mutate_misr_triangle_free_rectangles(
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    child = copy.deepcopy(instance)
    rects = child.get("rectangles", [])
    moves = ["add", "replace", "nudge", "resize", "delete"]
    if local_search in {"lp_dual_pivot", "sequence_pair_pivot", "program_coeff_pivot"}:
        moves += ["add", "add", "replace"]
    move = rng.choice(moves)
    if move == "delete" and len(rects) > n_min:
        del rects[rng.randrange(len(rects))]
    elif move == "add" and len(rects) < n_max:
        candidate = _best_triangle_free_addition(rects, rng, grid=grid)
        if candidate is not None:
            rects.append(candidate)
    elif move == "replace" and rects:
        idx = rng.randrange(len(rects))
        base = rects[:idx] + rects[idx + 1 :]
        candidate = _best_triangle_free_addition(base, rng, grid=grid)
        if candidate is not None:
            rects[:] = base + [candidate]
    elif rects:
        idx = rng.randrange(len(rects))
        x1, x2, y1, y2 = rects[idx]
        side = max(4, grid + 2)
        if move == "resize":
            x1 = max(0, min(side - 1, x1 + rng.choice([-1, 0])))
            x2 = max(x1 + 1, min(side, x2 + rng.choice([0, 1])))
            y1 = max(0, min(side - 1, y1 + rng.choice([-1, 0])))
            y2 = max(y1 + 1, min(side, y2 + rng.choice([0, 1])))
        else:
            dx, dy = rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1])
            x1 = max(0, min(side - 1, x1 + dx))
            x2 = max(x1 + 1, min(side, x2 + dx))
            y1 = max(0, min(side - 1, y1 + dy))
            y2 = max(y1 + 1, min(side, y2 + dy))
        rects[idx] = [x1, x2, y1, y2]
    child["schema"] = "misr_instance_v1"
    child["constraints"] = {"triangle_free": True}
    child["_representation"] = "triangle_free_rect"
    return child


def _best_triangle_free_addition(
    rects: list[list[int]],
    rng: random.Random,
    *,
    grid: int,
) -> list[int] | None:
    best: list[int] | None = None
    best_key: tuple[float, int, int, int, int, float] | None = None
    for candidate in _triangle_free_candidate_pool(rects, rng, grid=grid, count=max(96, 12 * max(1, len(rects)))):
        if not _can_add_triangle_free(rects, candidate):
            continue
        key = (*_triangle_free_key(rects + [candidate]), rng.random())
        if best_key is None or key > best_key:
            best_key = key
            best = candidate
    return best


def mutate_misr_quadratic_program(
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    target_n = max(n_min, min(n_max, len(instance.get("rectangles", [])) or n_min))
    payload = _quadratic_program_payload(
        instance.get("_representation_payload", {}),
        n=target_n,
        grid=grid,
    )
    coeffs = payload["coeffs"]
    moves = ["coeff", "coeff", "decoder", "composition"]
    if local_search == "program_coeff_pivot":
        moves += ["coeff", "coeff", "active_n", "refresh_block"]
    elif local_search == "lp_dual_pivot":
        moves += ["coeff", "decoder"]
    move = rng.choice(moves)
    if move == "coeff":
        name = rng.choice(tuple(coeffs))
        values = coeffs[name]
        idx = rng.randrange(len(values))
        bound = int(payload["coeff_bound"])
        values[idx] = max(-bound, min(bound, values[idx] + rng.choice([-2, -1, 1, 2])))
    elif move == "refresh_block":
        name = rng.choice(tuple(coeffs))
        bound = int(payload["coeff_bound"])
        values = coeffs[name]
        start = rng.randrange(len(values))
        for idx in range(start, min(len(values), start + rng.randrange(1, 4))):
            values[idx] = rng.randrange(-bound, bound + 1)
    elif move == "decoder":
        decoders = ["endpoints", "center_size", "thin_segments"]
        current = str(payload.get("decoder", "thin_segments"))
        choices = [decoder for decoder in decoders if decoder != current]
        payload["decoder"] = rng.choice(choices or decoders)
    elif move == "active_n":
        payload["active_n"] = max(n_min, min(n_max, int(payload["active_n"]) + rng.choice([-1, 1])))
    else:
        composition = list(payload.get("composition", [target_n]))
        if len(composition) >= 2:
            src, dst = rng.sample(range(len(composition)), 2)
            if composition[src] > 1:
                composition[src] -= 1
                composition[dst] += 1
        payload["composition"] = composition
    child = {
        "schema": "misr_instance_v1",
        "rectangles": _rectangles_from_quadratic_program_payload(payload, grid=grid),
        "constraints": {"triangle_free": True},
        "_representation": "quadratic_program_rectangles",
        "_representation_payload": payload,
    }
    return child


def mutate_misr_endpoint_sequence_pair(
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    payload = instance.get("_representation_payload", {})
    h_raw = payload.get("H") if isinstance(payload, dict) else None
    v_raw = payload.get("V") if isinstance(payload, dict) else None
    fallback_n = max(n_min, len(instance.get("rectangles", [])) or n_min)
    if h_raw is None or v_raw is None:
        h_raw, v_raw = misr_sequences.pair_from_rectangles(instance.get("rectangles", []))
        fallback_n = max(n_min, len(instance.get("rectangles", [])) or n_min)
    n = max(n_min, min(n_max, misr_sequences.infer_n(h_raw, v_raw, fallback=fallback_n)))
    h_seq, v_seq = misr_sequences.clean_pair(h_raw, v_raw, n=n)

    if local_search in {"sequence_pair_pivot", "lp_dual_pivot"}:
        h_seq, v_seq, mutation = _best_endpoint_sequence_neighbor(
            h_seq,
            v_seq,
            rng,
            n_max=n_max,
            allow_lift=local_search == "sequence_pair_pivot",
            trials=10 if local_search == "sequence_pair_pivot" else 6,
        )
    elif rng.random() < 0.08:
        h_seq, v_seq, generator = misr_sequences.seeded_pair(n, rng)
        mutation = f"{generator}_refresh"
    elif local_search == "motif_blowup" and rng.random() < 0.25:
        h_seq = misr_sequences.random_valid_sequence(n, rng)
        v_seq = misr_sequences.random_valid_sequence(n, rng)
        mutation = "random_sequence_refresh"
    else:
        strong = local_search in {"sequence_pair_pivot", "motif_blowup", "lp_dual_pivot"}
        allow_lift = local_search in {"sequence_pair_pivot", "motif_blowup"}
        h_seq, v_seq, mutation = misr_sequences.mutate_pair(
            h_seq,
            v_seq,
            rng,
            n_max=n_max,
            allow_lift=allow_lift,
            strong=strong,
        )

    rectangles = misr_sequences.rectangles_from_pair(h_seq, v_seq)
    child = {"schema": "misr_instance_v1", "rectangles": rectangles}
    child["_representation"] = "endpoint_sequence_pair"
    child["_representation_payload"] = misr_sequences.payload_for_pair(
        h_seq,
        v_seq,
        generator="mutated_endpoint_sequences",
        mutation=mutation,
    )
    return child


def _best_endpoint_sequence_neighbor(
    h_seq: misr_sequences.Seq,
    v_seq: misr_sequences.Seq,
    rng: random.Random,
    *,
    n_max: int,
    allow_lift: bool,
    trials: int,
) -> tuple[misr_sequences.Seq, misr_sequences.Seq, str]:
    candidates: list[tuple[misr_sequences.Seq, misr_sequences.Seq, str]] = [(h_seq[:], v_seq[:], "sequence_keep")]
    n = max(h_seq, default=0)
    if n > 0:
        for _ in range(max(1, trials)):
            h2, v2, mutation = misr_sequences.mutate_pair(
                h_seq,
                v_seq,
                rng,
                n_max=n_max,
                allow_lift=allow_lift,
                strong=True,
            )
            candidates.append((h2, v2, mutation))
        if rng.random() < 0.35:
            h2, v2, generator = misr_sequences.seeded_pair(n, rng)
            candidates.append((h2, v2, f"{generator}_refresh"))
    best = candidates[0]
    best_key = _endpoint_sequence_score_key(*best[:2])
    for candidate in candidates[1:]:
        key = _endpoint_sequence_score_key(candidate[0], candidate[1])
        if key > best_key:
            best = candidate
            best_key = key
    return best


def _endpoint_sequence_score_key(h_seq: misr_sequences.Seq, v_seq: misr_sequences.Seq) -> tuple[float, float, float, int]:
    try:
        rects = misr_sequences.rectangles_from_pair(h_seq, v_seq)
        cert = misr_scorer.score_instance({"rectangles": rects})
        n = max(1, int(cert["n"]))
        return (
            float(cert["score"]),
            float(cert["alpha_lp"]) / n,
            -float(cert["alpha_int"]) / n,
            n,
        )
    except Exception:
        return (-1.0, -1.0, -1.0, 0)


def mutate_unit_square(
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
    representation: str | None = None,
) -> dict[str, Any]:
    child = copy.deepcopy(instance)
    squares = child["squares"]
    moves = ["move", "duplicate", "delete"]
    if local_search == "primal_dual_lines":
        moves += ["move", "duplicate", "align_line"]
    elif local_search == "gadget_layer_mutation":
        moves += ["duplicate", "row_shift", "layer_shift"]
    elif local_search == "sqstab_local_hillclimb":
        moves += [
            "move",
            "align_line",
            "line_tighten",
            "canonical_shift",
            "random_restart",
        ]
    if representation == "line_square_incidence":
        moves += ["align_line"]
    elif representation == "threshold_layer_grammar":
        moves += ["layer_shift"]
    elif representation == "sqstab_exact_grid":
        moves += ["line_tighten", "canonical_shift", "random_restart"]
    move = rng.choice(moves)
    if move == "delete" and len(squares) > n_min:
        del squares[rng.randrange(len(squares))]
    elif move == "duplicate" and len(squares) < n_max and squares:
        x, y = squares[rng.randrange(len(squares))]
        squares.append([max(0, min(grid, x + rng.choice([-1, 0, 1]))), max(0, min(grid, y + rng.choice([-1, 0, 1])))])
    elif move == "row_shift" and squares:
        y = rng.choice(squares)[1]
        for sq in squares:
            if sq[1] == y and rng.random() < 0.5:
                sq[0] = max(0, min(grid, sq[0] + rng.choice([-1, 1])))
    elif move == "align_line" and len(squares) >= 2:
        idx = rng.randrange(len(squares))
        ref = squares[rng.randrange(len(squares))]
        if rng.random() < 0.5:
            squares[idx][0] = ref[0]
        else:
            squares[idx][1] = ref[1]
    elif move == "line_tighten" and len(squares) >= 2:
        side = max(1, int(child.get("side", 1) or 1))
        idx = rng.randrange(len(squares))
        ref = squares[rng.randrange(len(squares))]
        while ref is squares[idx] and len(squares) > 1:
            ref = squares[rng.randrange(len(squares))]
        if rng.random() < 0.5:
            squares[idx][0] = max(0, min(grid, ref[0] + rng.choice([-side, 0, side])))
        else:
            squares[idx][1] = max(0, min(grid, ref[1] + rng.choice([-side, 0, side])))
    elif move == "canonical_shift" and squares:
        min_x = min(sq[0] for sq in squares)
        min_y = min(sq[1] for sq in squares)
        for sq in squares:
            sq[0] = max(0, min(grid, sq[0] - min_x))
            sq[1] = max(0, min(grid, sq[1] - min_y))
    elif move == "random_restart":
        target = rng.randrange(n_min, max(n_min, n_max) + 1)
        side = max(1, grid + 1)
        seen: set[tuple[int, int]] = set()
        fresh_squares: list[list[int]] = []
        while len(fresh_squares) < target:
            candidate = (rng.randrange(side), rng.randrange(side))
            if candidate in seen:
                continue
            seen.add(candidate)
            fresh_squares.append([candidate[0], candidate[1]])
        squares[:] = fresh_squares
        child["side"] = rng.randrange(1, max(2, min(grid + 2, 4)) + 1)
    elif move == "layer_shift" and squares:
        payload = child.get("_representation_payload", {})
        assignments = payload.get("assignments", []) if isinstance(payload, dict) else []
        layers = sorted({row.get("layer") for row in assignments if isinstance(row, dict) and "layer" in row})
        layer = rng.choice(layers) if layers else rng.randrange(max(1, min(4, len(squares))))
        dx, dy = rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1])
        if dx == 0 and dy == 0:
            dx = 1
        for idx, sq in enumerate(squares):
            assigned = assignments[idx].get("layer") if idx < len(assignments) and isinstance(assignments[idx], dict) else idx % max(1, len(layers) or 1)
            if assigned == layer:
                sq[0] = max(0, min(grid, sq[0] + dx))
                sq[1] = max(0, min(grid, sq[1] + dy))
    elif squares:
        idx = rng.randrange(len(squares))
        squares[idx][0] = max(0, min(grid, squares[idx][0] + rng.choice([-1, 0, 1])))
        squares[idx][1] = max(0, min(grid, squares[idx][1] + rng.choice([-1, 0, 1])))
    if local_search == "sqstab_local_hillclimb" or representation == "sqstab_exact_grid":
        child = _sqstab_guided_neighbor(child, rng, grid=grid, n_min=n_min, n_max=n_max)
    return child


def _sqstab_guided_neighbor(
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    candidates = [copy.deepcopy(instance)]
    trials = 4 if len(instance.get("squares", [])) <= 48 else 2
    for _ in range(trials):
        trial = copy.deepcopy(instance)
        squares = trial.get("squares", [])
        if not isinstance(squares, list):
            continue
        move = rng.choice(["tighten", "add_random", "replace_random", "drop_slack", "canonical"])
        if move == "tighten" and len(squares) >= 2:
            side = max(1, int(trial.get("side", 1) or 1))
            idx = rng.randrange(len(squares))
            ref = squares[rng.randrange(len(squares))]
            if rng.random() < 0.5:
                squares[idx][0] = max(0, int(ref[0]) + rng.choice([-side, 0, side]))
            else:
                squares[idx][1] = max(0, int(ref[1]) + rng.choice([-side, 0, side]))
        elif move in {"add_random", "replace_random"}:
            seen = {tuple(row) for row in squares if isinstance(row, list) and len(row) >= 2}
            for _attempt in range(20):
                candidate = (rng.randrange(max(1, grid + 1)), rng.randrange(max(1, grid + 1)))
                if candidate in seen:
                    continue
                if move == "add_random" and len(squares) < n_max:
                    squares.append([candidate[0], candidate[1]])
                elif squares:
                    squares[rng.randrange(len(squares))] = [candidate[0], candidate[1]]
                break
        elif move == "drop_slack" and len(squares) > n_min:
            del squares[rng.randrange(len(squares))]
        elif move == "canonical" and squares:
            trial["squares"] = _normalize_square_coordinates([[int(row[0]), int(row[1])] for row in squares if isinstance(row, list) and len(row) >= 2])
        candidates.append(trial)

    best = candidates[0]
    best_key = _sqstab_score_key(best)
    for candidate in candidates[1:]:
        key = _sqstab_score_key(candidate)
        if key > best_key:
            best = candidate
            best_key = key
    return best


def _sqstab_score_key(instance: dict[str, Any]) -> tuple[float, float, float, int]:
    squares = instance.get("squares", [])
    if not isinstance(squares, list) or not squares:
        return (-1.0, -1.0, -1.0, 0)
    try:
        clean = {
            "squares": _normalize_square_coordinates(
                [[int(row[0]), int(row[1])] for row in squares if isinstance(row, list) and len(row) >= 2]
            ),
            "side": instance.get("side", 1),
        }
        if len(clean["squares"]) <= 48:
            cert = unit_square_scorer.score_instance(clean)
            return (
                float(cert["score"]),
                float(cert["tau_int"]),
                -float(cert["tau_lp"]),
                len(clean["squares"]),
            )
        parsed = [unit_square_scorer.parse_point(row) for row in clean["squares"]]
        side = unit_square_scorer.parse_number(clean.get("side", 1))
        _lines, masks = unit_square_scorer._line_universe(parsed, side=side)
        all_squares = (1 << len(parsed)) - 1
        greedy = len(unit_square_scorer._greedy_cover(masks, all_squares))
        max_freq = max((bin(mask).count("1") for mask in masks), default=1)
        fractional_hint = max(1.0, len(parsed) / max_freq)
        return (greedy / fractional_hint, float(greedy), -float(max_freq), len(parsed))
    except Exception:
        return (-1.0, -1.0, -1.0, 0)


def mutate_guillotine(
    local_search: str,
    instance: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
    representation: str | None = None,
) -> dict[str, Any]:
    child = copy.deepcopy(instance)
    rects = child["rectangles"]
    occupied = {(r[0], r[2]) for r in rects}
    side = _guillotine_dynamic_side(grid=grid, n=max(n_min, len(rects) + 1), rects=rects)
    moves = ["move", "resize", "add", "delete"]
    if local_search == "packing_resize":
        moves += ["witness_gap", "bar_replace", "add"]
    elif local_search == "weak_cut_blockers":
        moves += ["add", "move", "cut_blocker"]
    elif local_search == "recursive_gadget_assembly":
        moves += ["add", "add", "bar_replace", "motif_copy", "insert_obstruction", "recursive_tile"]
    elif local_search == "witness_breaking":
        moves += ["witness_gap", "witness_gap", "witness_bridge", "bar_replace", "cut_blocker", "motif_copy"]
    if representation == "sequence_pair_packing":
        moves += ["swap_order"]
    elif representation == "recursive_obstruction_grammar":
        moves += ["cut_blocker", "motif_copy", "insert_obstruction"]
    move = rng.choice(moves)
    if move == "delete" and len(rects) > n_min:
        del rects[rng.randrange(len(rects))]
    elif move == "add" and len(rects) < n_max:
        for _ in range(48):
            rect = _guillotine_random_rect(rng, side=side)
            if not _guillotine_overlaps_any(rect, rects):
                rects.append(rect)
                break
    elif move == "bar_replace" and rects:
        _guillotine_replace_with_random_bar(rects, rng, grid=grid)
    elif move == "cut_blocker" and len(rects) < n_max:
        axis = rng.choice(["x", "y"])
        coord = rng.randrange(max(1, grid))
        for offset in range(grid):
            if len(rects) >= n_max:
                break
            x, y = (coord, offset) if axis == "x" else (offset, coord)
            rect = [x, x + 1, y, y + 1]
            if (x, y) not in occupied and not _guillotine_overlaps_any(rect, rects):
                rects.append(rect)
                occupied.add((x, y))
            if rng.random() < 0.35:
                break
    elif move == "insert_obstruction":
        motif = _guillotine_obstruction_rectangles(rng, grid=grid, n=5)
        next_rects = motif[:]
        for rect in rects:
            if len(next_rects) >= n_max:
                break
            if not _guillotine_overlaps_any(rect, next_rects):
                next_rects.append(rect)
        rects[:] = next_rects
    elif move == "witness_gap":
        _guillotine_witness_gap_closure(rects, rng, grid=grid)
    elif move == "witness_bridge" and len(rects) < n_max:
        if not _guillotine_witness_gap_closure(rects, rng, grid=grid):
            _guillotine_witness_bridge(rects, rng, grid=grid)
    elif move == "recursive_tile" and len(rects) < n_max:
        target = min(n_max, len(rects) + rng.randrange(5, min(16, max(6, n_max - len(rects) + 1))))
        motif = _guillotine_obstruction_rectangles(rng, grid=grid, n=target)
        for rect in motif:
            if len(rects) >= n_max:
                break
            if not _guillotine_overlaps_any(rect, rects):
                rects.append(rect)
                occupied.add((rect[0], rect[2]))
    elif move == "motif_copy" and len(rects) < n_max and rects:
        motif = rng.sample(rects, k=min(len(rects), rng.randrange(1, min(4, len(rects)) + 1)))
        dx, dy = rng.choice([-3, -2, 2, 3]), rng.choice([-3, -2, 2, 3])
        for r in motif:
            if len(rects) >= n_max:
                break
            width = max(1, r[1] - r[0])
            height = max(1, r[3] - r[2])
            x = max(0, min(side - width, r[0] + dx))
            y = max(0, min(side - height, r[2] + dy))
            rect = [x, x + width, y, y + height]
            if not _guillotine_overlaps_any(rect, rects):
                rects.append(rect)
                occupied.add((x, y))
    elif move == "swap_order" and len(rects) >= 2:
        i, j = rng.sample(range(len(rects)), 2)
        rects[i], rects[j] = rects[j], rects[i]
    elif move == "resize" and rects:
        idx = rng.randrange(len(rects))
        x1, x2, y1, y2 = rects[idx]
        x1 = max(0, min(side - 1, x1 + rng.choice([-1, 0])))
        x2 = max(x1 + 1, min(side, x2 + rng.choice([0, 1])))
        y1 = max(0, min(side - 1, y1 + rng.choice([-1, 0])))
        y2 = max(y1 + 1, min(side, y2 + rng.choice([0, 1])))
        rects[idx] = [x1, x2, y1, y2]
    elif rects:
        idx = rng.randrange(len(rects))
        x, y = rects[idx][0], rects[idx][2]
        width = max(1, rects[idx][1] - rects[idx][0])
        height = max(1, rects[idx][3] - rects[idx][2])
        for _ in range(20):
            nx = max(0, min(side - width, x + rng.choice([-1, 0, 1])))
            ny = max(0, min(side - height, y + rng.choice([-1, 0, 1])))
            if (nx, ny) not in occupied or (nx, ny) == (x, y):
                rects[idx] = [nx, nx + width, ny, ny + height]
                break
    if local_search in {"packing_resize", "witness_breaking"} or representation == "recursive_obstruction_grammar":
        _guillotine_guided_nonseparability_step(child, rng, grid=grid, n_min=n_min, n_max=n_max)
    return child


def _guillotine_overlaps_any(rect: list[int], rects: list[list[int]]) -> bool:
    return any(
        max(rect[0], other[0]) < min(rect[1], other[1])
        and max(rect[2], other[2]) < min(rect[3], other[3])
        for other in rects
    )


def _guillotine_random_k_mask(n: int, k: int, rng: random.Random) -> int:
    if k <= 0:
        return 0
    chosen = set(rng.sample(range(n), k=min(k, n)))
    mask = 0
    for idx in chosen:
        mask |= 1 << idx
    return mask


def _guillotine_separable_witness_mask(
    rects: list[list[int]],
    rng: random.Random,
    *,
    exact_max_n: int = 12,
    sample_limit: int = 256,
) -> tuple[int, list[guillotine_scorer.Box]]:
    rectangles = guillotine_scorer._validate_rectangles(rects)
    n = len(rectangles)
    if n <= 1:
        return 0, rectangles
    k = n // 2 + 1
    if n <= exact_max_n:
        masks = [guillotine_scorer._subset_mask(combo) for combo in itertools.combinations(range(n), k)]
        rng.shuffle(masks)
    else:
        masks = []
        seen: set[int] = set()
        attempts = 0
        while len(masks) < sample_limit and attempts < sample_limit * 4:
            attempts += 1
            mask = _guillotine_random_k_mask(n, k, rng)
            if mask in seen:
                continue
            seen.add(mask)
            masks.append(mask)
    for mask in masks:
        if guillotine_scorer._is_guillotine_separable_subset(rectangles, mask):
            return mask, rectangles
    return 0, rectangles


def _open_axis_overlap(lo_a: int, hi_a: int, lo_b: int, hi_b: int) -> bool:
    return max(lo_a, lo_b) < min(hi_a, hi_b)


def _guillotine_try_close_projection_gap(
    rects: list[list[int]],
    first_idx: int,
    second_idx: int,
    *,
    axis: str,
    side: int,
) -> bool:
    if first_idx == second_idx:
        return False
    a = rects[first_idx]
    b = rects[second_idx]
    candidate = [list(rect) for rect in rects]
    if axis == "x":
        if _open_axis_overlap(a[2], a[3], b[2], b[3]):
            return False
        if a[1] <= b[0]:
            candidate[first_idx][1] = min(side, max(a[1], b[0] + 1))
        elif b[1] <= a[0]:
            candidate[second_idx][1] = min(side, max(b[1], a[0] + 1))
        else:
            return False
        changed_idx = first_idx if candidate[first_idx] != a else second_idx
    else:
        if _open_axis_overlap(a[0], a[1], b[0], b[1]):
            return False
        if a[3] <= b[2]:
            candidate[first_idx][3] = min(side, max(a[3], b[2] + 1))
        elif b[3] <= a[2]:
            candidate[second_idx][3] = min(side, max(b[3], a[2] + 1))
        else:
            return False
        changed_idx = first_idx if candidate[first_idx] != a else second_idx
    changed = candidate[changed_idx]
    if changed[0] >= changed[1] or changed[2] >= changed[3]:
        return False
    if _guillotine_overlaps_any(changed, candidate[:changed_idx] + candidate[changed_idx + 1 :]):
        return False
    rects[:] = candidate
    return True


def _guillotine_witness_gap_closure(rects: list[list[int]], rng: random.Random, *, grid: int) -> bool:
    if len(rects) < 2:
        return False
    try:
        witness, rectangles = _guillotine_separable_witness_mask(
            rects,
            rng,
            exact_max_n=12,
            sample_limit=256,
        )
    except Exception:
        return False
    if witness == 0:
        return False
    side = _guillotine_dynamic_side(grid=grid, n=len(rects) + 1, rects=rects)
    axes = ["x", "y"]
    rng.shuffle(axes)
    for axis in axes:
        components = guillotine_scorer._projection_components(rectangles, witness, axis)
        if len(components) <= 1:
            continue
        rng.shuffle(components)
        for left_pos, left_mask in enumerate(components):
            for right_mask in components[left_pos + 1 :]:
                left_members = list(guillotine_scorer._bits(left_mask))
                right_members = list(guillotine_scorer._bits(right_mask))
                rng.shuffle(left_members)
                rng.shuffle(right_members)
                for first_idx in left_members:
                    for second_idx in right_members:
                        if _guillotine_try_close_projection_gap(
                            rects,
                            first_idx,
                            second_idx,
                            axis=axis,
                            side=side,
                        ):
                            return True
    return False


def _guillotine_replace_with_random_bar(rects: list[list[int]], rng: random.Random, *, grid: int) -> bool:
    if not rects:
        return False
    idx = rng.randrange(len(rects))
    old = list(rects[idx])
    side = _guillotine_dynamic_side(grid=grid, n=len(rects), rects=rects)
    others = rects[:idx] + rects[idx + 1 :]
    for _ in range(96):
        rect = _guillotine_random_rect(rng, side=side)
        if not _guillotine_overlaps_any(rect, others):
            rects[idx] = rect
            return True
    rects[idx] = old
    return False


def _guillotine_witness_bridge(rects: list[list[int]], rng: random.Random, *, grid: int) -> bool:
    if len(rects) < 2:
        return False
    try:
        witness, rectangles = _guillotine_separable_witness_mask(
            rects,
            rng,
            exact_max_n=12,
            sample_limit=256,
        )
    except Exception:
        return False
    if witness == 0:
        return False
    axes = ["x", "y"]
    rng.shuffle(axes)
    side = _guillotine_dynamic_side(grid=grid, n=len(rects) + 1, rects=rects)
    for axis in axes:
        components = guillotine_scorer._projection_components(rectangles, witness, axis)
        if len(components) <= 1:
            continue
        component_ranges = []
        for mask in components:
            members = list(guillotine_scorer._bits(mask))
            if axis == "x":
                lo = min(rects[idx][0] for idx in members)
                hi = max(rects[idx][1] for idx in members)
            else:
                lo = min(rects[idx][2] for idx in members)
                hi = max(rects[idx][3] for idx in members)
            component_ranges.append((lo, hi))
        component_ranges.sort()
        for (_, left_hi), (right_lo, _) in zip(component_ranges, component_ranges[1:]):
            if left_hi > right_lo:
                continue
            if axis == "x":
                x1 = max(0, min(side - 1, left_hi - 1))
                x2 = max(x1 + 1, min(side, right_lo + 1))
                for y in range(side):
                    rect = [x1, x2, y, y + 1]
                    if not _guillotine_overlaps_any(rect, rects):
                        rects.append(rect)
                        return True
            else:
                y1 = max(0, min(side - 1, left_hi - 1))
                y2 = max(y1 + 1, min(side, right_lo + 1))
                for x in range(side):
                    rect = [x, x + 1, y1, y2]
                    if not _guillotine_overlaps_any(rect, rects):
                        rects.append(rect)
                        return True
    return False


def _guillotine_guided_nonseparability_step(
    child: dict[str, Any],
    rng: random.Random,
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> None:
    rects = child.get("rectangles", [])
    if not isinstance(rects, list) or not rects:
        return
    best_rects = [list(rect) for rect in rects]
    best_key = _guillotine_nonseparability_key(best_rects)
    for _ in range(3):
        trial = [list(rect) for rect in best_rects]
        side = _guillotine_dynamic_side(grid=grid, n=max(n_min, len(trial) + 1), rects=trial)
        move = rng.choice(["gap", "bridge", "bar_add", "replace", "resize", "endpoint"])
        if move == "gap":
            _guillotine_witness_gap_closure(trial, rng, grid=grid)
        elif move == "bridge" and len(trial) < n_max:
            if not _guillotine_witness_gap_closure(trial, rng, grid=grid):
                _guillotine_witness_bridge(trial, rng, grid=grid)
        elif move == "bar_add" and len(trial) < n_max:
            for _attempt in range(32):
                rect = _guillotine_random_rect(rng, side=side)
                if not _guillotine_overlaps_any(rect, trial):
                    trial.append(rect)
                    break
        elif move == "replace" and len(trial) > n_min:
            _guillotine_replace_with_random_bar(trial, rng, grid=grid)
        elif move == "endpoint" and trial:
            idx = rng.randrange(len(trial))
            rect = list(trial[idx])
            side_idx = rng.randrange(4)
            delta = rng.choice([-2, -1, 1, 2])
            if side_idx == 0:
                rect[0] = max(0, min(rect[1] - 1, rect[0] + delta))
            elif side_idx == 1:
                rect[1] = max(rect[0] + 1, min(side, rect[1] + delta))
            elif side_idx == 2:
                rect[2] = max(0, min(rect[3] - 1, rect[2] + delta))
            else:
                rect[3] = max(rect[2] + 1, min(side, rect[3] + delta))
            if not _guillotine_overlaps_any(rect, trial[:idx] + trial[idx + 1 :]):
                trial[idx] = rect
        elif trial:
            idx = rng.randrange(len(trial))
            x1, x2, y1, y2 = trial[idx]
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            if rng.random() < 0.5:
                width = max(1, min(side, width + rng.choice([-1, 1, 2])))
            else:
                height = max(1, min(side, height + rng.choice([-1, 1, 2])))
            x1 = max(0, min(side - width, x1))
            y1 = max(0, min(side - height, y1))
            trial[idx] = [x1, x1 + width, y1, y1 + height]
            if _guillotine_overlaps_any(trial[idx], trial[:idx] + trial[idx + 1 :]):
                continue
        key = _guillotine_nonseparability_key(trial)
        if key >= best_key:
            best_key = key
            best_rects = trial
    child["rectangles"] = _guillotine_canonicalize(best_rects)


def _guillotine_nonseparability_key(rects: list[list[int]]) -> tuple[float, float, int, float]:
    try:
        rectangles = guillotine_scorer._validate_rectangles(rects)
        threshold = guillotine_scorer._k_subset_nonseparability_summary(
            rectangles,
            exact_max_n=12,
            sample_limit=256,
        )
    except Exception:
        return (-1.0, -1.0, -1, -1.0)
    n = len(rectangles)
    first_cut = 0.0
    if n:
        x_coords = sorted({coord for x1, x2, _, _ in rectangles for coord in (x1, x2)})
        y_coords = sorted({coord for _, _, y1, y2 in rectangles for coord in (y1, y2)})
        candidates = []
        for axis, coords in (
            ("x", guillotine_scorer._candidate_cut_coordinates(x_coords)),
            ("y", guillotine_scorer._candidate_cut_coordinates(y_coords)),
        ):
            for coord in coords:
                low, high, crossed = guillotine_scorer._partition(rectangles, (1 << n) - 1, axis, coord)
                if low and high:
                    candidates.append(guillotine_scorer._popcount(crossed) / n)
        first_cut = min(candidates, default=0.0)
    return (
        float(threshold["threshold_nonseparable_fraction"]),
        first_cut,
        n,
        -float(threshold["threshold_separable_count"]),
    )


def initial_instance(problem: str, rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    return GENERATORS[problem](rng, n=n, grid=grid)
