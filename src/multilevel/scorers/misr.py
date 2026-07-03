from __future__ import annotations

import time
import warnings
from typing import Any

import numpy as np
from scipy.optimize import OptimizeWarning, linprog

from multilevel.canonical import attach_certificate_hash
from multilevel.numbers import json_box, parse_box

Box = tuple[Any, Any, Any, Any]


def _validate_rectangles(raw: list[list[Any]]) -> list[Box]:
    rectangles = [parse_box(row) for row in raw]
    for rect in rectangles:
        x1, x2, y1, y2 = rect
        if not (x1 < x2 and y1 < y2):
            raise ValueError(f"invalid rectangle with nonpositive area: {rect!r}")
    return rectangles


def _intersects(a: Box, b: Box) -> bool:
    ax1, ax2, ay1, ay2 = a
    bx1, bx2, by1, by2 = b
    return max(ax1, bx1) <= min(ax2, bx2) and max(ay1, by1) <= min(ay2, by2)


def _intersection_graph(rectangles: list[Box]) -> list[int]:
    n = len(rectangles)
    adj = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if _intersects(rectangles[i], rectangles[j]):
                adj[i] |= 1 << j
                adj[j] |= 1 << i
    return adj


def _triangle_witness(adj: list[int]) -> list[int] | None:
    n = len(adj)
    for i in range(n):
        for j in range(i + 1, n):
            if not (adj[i] & (1 << j)):
                continue
            common = adj[i] & adj[j] & ~((1 << (j + 1)) - 1)
            if common:
                k = (common & -common).bit_length() - 1
                return [i, j, k]
    return None


def _is_triangle_free(adj: list[int]) -> bool:
    return _triangle_witness(adj) is None


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def _popcount(mask: int) -> int:
    return bin(mask).count("1")


def _maximal_cliques(adj: list[int]) -> list[list[int]]:
    n = len(adj)
    cliques: list[list[int]] = []

    def bronk(r: int, p: int, x: int) -> None:
        if p == 0 and x == 0:
            cliques.append(list(_bits(r)))
            return
        union = p | x
        pivot = max(_bits(union), key=lambda v: _popcount(p & adj[v]), default=-1)
        choices = p & ~adj[pivot] if pivot >= 0 else p
        for v in list(_bits(choices)):
            bit = 1 << v
            bronk(r | bit, p & adj[v], x & adj[v])
            p &= ~bit
            x |= bit

    bronk(0, (1 << n) - 1, 0)
    return [clique for clique in cliques if clique]


def _color_sort(candidates: int, adj: list[int]) -> tuple[list[int], list[int]]:
    order: list[int] = []
    bounds: list[int] = []
    remaining = candidates
    color = 0
    while remaining:
        color += 1
        available = remaining
        while available:
            v = (available & -available).bit_length() - 1
            order.append(v)
            bounds.append(color)
            remaining &= ~(1 << v)
            available &= ~(1 << v)
            available &= ~adj[v]
    return order, bounds


def _maximum_clique(adj: list[int]) -> list[int]:
    n = len(adj)
    best: list[int] = []

    def expand(chosen: list[int], candidates: int) -> None:
        nonlocal best
        if not candidates:
            if len(chosen) > len(best):
                best = chosen[:]
            return
        order, bounds = _color_sort(candidates, adj)
        for idx in range(len(order) - 1, -1, -1):
            v = order[idx]
            if len(chosen) + bounds[idx] <= len(best):
                return
            bit = 1 << v
            if not (candidates & bit):
                continue
            expand(chosen + [v], candidates & adj[v])
            candidates &= ~bit

    expand([], (1 << n) - 1)
    return sorted(best)


def _maximum_independent_set(adj: list[int]) -> list[int]:
    n = len(adj)
    all_mask = (1 << n) - 1
    complement = [all_mask & ~(1 << i) & ~adj[i] for i in range(n)]
    return _maximum_clique(complement)


def score_instance(instance: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    rectangles = _validate_rectangles(instance["rectangles"])
    constraints = instance.get("constraints", {})
    if not isinstance(constraints, dict):
        constraints = {}
    require_triangle_free = bool(constraints.get("triangle_free"))
    n = len(rectangles)
    adj = _intersection_graph(rectangles)
    triangle = _triangle_witness(adj)
    triangle_free = triangle is None
    if require_triangle_free and not triangle_free:
        raise ValueError(f"MISR instance violates triangle-free constraint: {triangle}")
    cliques = _maximal_cliques(adj)

    if n == 0:
        raise ValueError("MISR instance must contain at least one rectangle")

    a_ub = np.zeros((len(cliques), n), dtype=float)
    for row, clique in enumerate(cliques):
        for vertex in clique:
            a_ub[row, vertex] = 1.0
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Unrecognized options detected: .*'threads'",
            category=OptimizeWarning,
        )
        result = linprog(
            c=-np.ones(n),
            A_ub=a_ub,
            b_ub=np.ones(len(cliques)),
            bounds=[(0.0, None)] * n,
            method="highs",
            options={"threads": 1},
        )
    if not result.success:
        raise RuntimeError(f"MISR LP failed: {result.message}")

    independent = _maximum_independent_set(adj)
    alpha_int = len(independent)
    alpha_lp = float(-result.fun)
    score = alpha_lp / alpha_int if alpha_int else float("inf")

    dual = {}
    marginals = getattr(getattr(result, "ineqlin", None), "marginals", None)
    if marginals is not None:
        dual = {f"clique_{i}": float(max(0.0, -value)) for i, value in enumerate(marginals)}

    cert = {
        "schema": "misr_certificate_v1",
        "problem": "misr",
        "rectangles": [json_box(rect) for rect in rectangles],
        "n": n,
        "alpha_int": alpha_int,
        "alpha_lp": alpha_lp,
        "score": score,
        "constraints": constraints,
        "triangle_free": triangle_free,
        "triangle_witness": triangle,
        "max_clique_size": max((len(clique) for clique in cliques), default=0),
        "maximal_cliques": cliques,
        "lp_primal": {str(i): float(value) for i, value in enumerate(result.x) if abs(value) > 1e-10},
        "lp_dual": dual,
        "integer_solution": independent,
        "intersection_edges": [
            [i, j] for i in range(n) for j in range(i + 1, n) if adj[i] & (1 << j)
        ],
        "solver": {
            "integer_solver": "branch_and_bound_maximum_independent_set",
            "lp_solver": "scipy.optimize.linprog",
            "lp_method": "highs",
            "tolerance": 1e-8,
        },
        "solver_status": "optimal",
        "exact_runtime_seconds": time.perf_counter() - start,
        "constraint_count": len(cliques),
    }
    return attach_certificate_hash(cert)


def verify_certificate(cert: dict[str, Any], tolerance: float = 1e-8) -> bool:
    instance = {"rectangles": cert["rectangles"]}
    if isinstance(cert.get("constraints"), dict):
        instance["constraints"] = cert["constraints"]
    recomputed = score_instance(instance)
    return (
        cert.get("alpha_int") == recomputed.get("alpha_int")
        and abs(float(cert.get("alpha_lp")) - float(recomputed.get("alpha_lp"))) <= tolerance
        and abs(float(cert.get("score")) - float(recomputed.get("score"))) <= tolerance
        and cert.get("triangle_free") == recomputed.get("triangle_free")
    )
