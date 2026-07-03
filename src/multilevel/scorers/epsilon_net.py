from __future__ import annotations

import itertools
import math
import time
from typing import Any

from multilevel.canonical import attach_certificate_hash
from multilevel.numbers import json_point, parse_point


def _normal_directions(points: list[tuple]) -> list[tuple[float, float]]:
    critical = {0.0, math.pi}
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            dx = float(points[j][0] - points[i][0])
            dy = float(points[j][1] - points[i][1])
            if dx == 0.0 and dy == 0.0:
                continue
            angle = (math.atan2(dy, dx) + math.pi / 2.0) % (2.0 * math.pi)
            critical.add(angle)
            critical.add((angle + math.pi) % (2.0 * math.pi))
    angles = sorted(critical)
    samples = []
    for angle in angles:
        samples.append(angle)
    wrapped = angles + [angles[0] + 2.0 * math.pi]
    for a, b in zip(wrapped, wrapped[1:]):
        mid = (a + b) / 2.0
        samples.append(mid % (2.0 * math.pi))
    directions = []
    seen = set()
    for angle in samples:
        nx = round(math.cos(angle), 15)
        ny = round(math.sin(angle), 15)
        key = (nx, ny)
        if key not in seen:
            seen.add(key)
            directions.append((nx, ny))
    return directions


def _projection(point, normal: tuple[float, float]) -> float:
    return float(point[0]) * normal[0] + float(point[1]) * normal[1]


def _find_witness(
    points: list[tuple],
    net: tuple[int, ...],
    threshold: int,
    directions: list[tuple[float, float]],
) -> dict[str, Any] | None:
    net_set = set(net)
    if not net:
        return {
            "net": [],
            "normal": [1.0, 0.0],
            "strict_threshold": "-inf",
            "contained": list(range(len(points))),
        }
    for normal in directions:
        max_net = max(_projection(points[i], normal) for i in net)
        contained = [
            i
            for i, point in enumerate(points)
            if i not in net_set and _projection(point, normal) > max_net + 1e-10
        ]
        if len(contained) >= threshold:
            return {
                "net": list(net),
                "normal": [normal[0], normal[1]],
                "strict_threshold": max_net,
                "contained": contained,
            }
    return None


def score_instance(instance: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    points = [parse_point(row) for row in instance["points"]]
    threshold = int(instance["threshold"])
    k = int(instance["k"])
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    if k < 0 or k > len(points):
        raise ValueError("k must be between 0 and number of points")
    if threshold > len(points):
        raise ValueError("threshold cannot exceed number of points")

    directions = _normal_directions(points)
    witnesses = []
    missing = []
    for net in itertools.combinations(range(len(points)), k):
        witness = _find_witness(points, net, threshold, directions)
        if witness is None:
            missing.append(list(net))
        else:
            witnesses.append(witness)

    epsilon = threshold / len(points)
    lower_bound_ratio = (k + 1) * epsilon
    exact = not missing
    cert = {
        "schema": "epsilon_net_certificate_v1",
        "problem": "epsilon_net",
        "points": [json_point(point) for point in points],
        "n": len(points),
        "threshold": threshold,
        "epsilon": epsilon,
        "k": k,
        "score": lower_bound_ratio if exact else 0.0,
        "lower_bound_ratio": lower_bound_ratio,
        "exact_enumeration": True,
        "all_k_subsets_fail": exact,
        "num_k_subsets": math.comb(len(points), k),
        "num_witness_halfplanes": len(witnesses),
        "witnesses": witnesses,
        "missing_witness_nets": missing,
        "direction_count": len(directions),
        "solver": {
            "solver": "exact_k_subset_enumeration",
            "halfplane_family": "critical_normal_directions",
            "projection_tolerance": 1e-10,
            "num_directions": len(directions),
        },
        "solver_status": "optimal" if exact else "not_counterexample",
        "exact_runtime_seconds": time.perf_counter() - start,
    }
    return attach_certificate_hash(cert)


def verify_certificate(cert: dict[str, Any], tolerance: float = 1e-8) -> bool:
    recomputed = score_instance(
        {"points": cert["points"], "threshold": cert["threshold"], "k": cert["k"]}
    )
    return (
        cert.get("all_k_subsets_fail") == recomputed.get("all_k_subsets_fail")
        and cert.get("num_k_subsets") == recomputed.get("num_k_subsets")
        and abs(float(cert.get("score")) - float(recomputed.get("score"))) <= tolerance
    )
