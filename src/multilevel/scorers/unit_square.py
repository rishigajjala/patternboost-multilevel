from __future__ import annotations

import math
import time
import warnings
from fractions import Fraction
from typing import Any

import numpy as np
from scipy.optimize import OptimizeWarning, linprog

from multilevel.canonical import attach_certificate_hash
from multilevel.numbers import json_number, json_point, parse_number, parse_point

Interval = tuple[Fraction, Fraction]


def _axis_patterns(intervals: list[Interval]) -> list[tuple[Fraction, tuple[int, ...]]]:
    endpoints = sorted({value for interval in intervals for value in interval})
    probes = set(endpoints)
    for a, b in zip(endpoints, endpoints[1:]):
        if a < b:
            probes.add((a + b) / 2)
    patterns: dict[tuple[int, ...], Fraction] = {}
    for probe in sorted(probes):
        active = tuple(i for i, (lo, hi) in enumerate(intervals) if lo <= probe <= hi)
        if active and active not in patterns:
            patterns[active] = probe
    return [(coord, pattern) for pattern, coord in sorted(patterns.items(), key=lambda item: item[1])]


def _line_universe(squares: list[tuple[Fraction, Fraction]], side: Fraction = Fraction(1, 1)):
    x_intervals = [(x, x + side) for x, _ in squares]
    y_intervals = [(y, y + side) for _, y in squares]
    vertical = _axis_patterns(x_intervals)
    horizontal = _axis_patterns(y_intervals)
    line_masks: list[int] = []
    lines: list[dict[str, Any]] = []
    for idx, (coord, pattern) in enumerate(vertical):
        mask = sum(1 << square for square in pattern)
        line_masks.append(mask)
        lines.append({"id": f"v{idx}", "axis": "vertical", "coordinate": json_number(coord)})
    for idx, (coord, pattern) in enumerate(horizontal):
        mask = sum(1 << square for square in pattern)
        line_masks.append(mask)
        lines.append({"id": f"h{idx}", "axis": "horizontal", "coordinate": json_number(coord)})
    return lines, line_masks


def _greedy_cover(line_masks: list[int], all_squares: int) -> list[int]:
    covered = 0
    chosen: list[int] = []
    while covered != all_squares:
        best = max(
            range(len(line_masks)),
            key=lambda idx: _popcount(line_masks[idx] & ~covered),
        )
        gain = line_masks[best] & ~covered
        if gain == 0:
            raise ValueError("line universe does not cover all squares")
        chosen.append(best)
        covered |= line_masks[best]
    return chosen


def _popcount(mask: int) -> int:
    return bin(mask).count("1")


def _minimum_set_cover(line_masks: list[int], n_squares: int) -> list[int]:
    all_squares = (1 << n_squares) - 1
    lines_by_square: list[list[int]] = [[] for _ in range(n_squares)]
    for line, mask in enumerate(line_masks):
        for square in range(n_squares):
            if mask & (1 << square):
                lines_by_square[square].append(line)
    best = _greedy_cover(line_masks, all_squares)
    max_gain = max(_popcount(mask) for mask in line_masks)

    def lower_bound(uncovered: int) -> int:
        return math.ceil(_popcount(uncovered) / max_gain) if max_gain else 10**9

    def dfs(covered: int, chosen: list[int], chosen_mask: int) -> None:
        nonlocal best
        if covered == all_squares:
            if len(chosen) < len(best):
                best = chosen[:]
            return
        uncovered = all_squares & ~covered
        if len(chosen) + lower_bound(uncovered) >= len(best):
            return
        square = min(
            (s for s in range(n_squares) if uncovered & (1 << s)),
            key=lambda s: sum(1 for line in lines_by_square[s] if not (chosen_mask & (1 << line))),
        )
        candidates = sorted(
            (line for line in lines_by_square[square] if not (chosen_mask & (1 << line))),
            key=lambda line: _popcount(line_masks[line] & uncovered),
            reverse=True,
        )
        for line in candidates:
            gain = line_masks[line] & uncovered
            if gain:
                dfs(covered | line_masks[line], chosen + [line], chosen_mask | (1 << line))

    dfs(0, [], 0)
    return sorted(best)


def score_instance(instance: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    squares = [parse_point(row) for row in instance["squares"]]
    if not squares:
        raise ValueError("unit-square instance must contain at least one square")
    side = parse_number(instance.get("side", 1))
    if side <= 0:
        raise ValueError("unit-square side length must be positive")
    lines, line_masks = _line_universe(squares, side=side)
    n_squares = len(squares)
    n_lines = len(lines)

    incidence = np.zeros((n_squares, n_lines), dtype=float)
    incidence_lists: list[list[str]] = []
    for square in range(n_squares):
        ids: list[str] = []
        for line, mask in enumerate(line_masks):
            if mask & (1 << square):
                incidence[square, line] = 1.0
                ids.append(lines[line]["id"])
        incidence_lists.append(ids)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Unrecognized options detected: .*'threads'",
            category=OptimizeWarning,
        )
        result = linprog(
            c=np.ones(n_lines),
            A_ub=-incidence,
            b_ub=-np.ones(n_squares),
            bounds=[(0.0, None)] * n_lines,
            method="highs",
            options={"threads": 1},
        )
    if not result.success:
        raise RuntimeError(f"unit-square LP failed: {result.message}")

    chosen_lines = _minimum_set_cover(line_masks, n_squares)
    tau_int = len(chosen_lines)
    tau_lp = float(result.fun)
    score = tau_int / tau_lp if tau_lp > 0 else float("inf")

    dual = {}
    marginals = getattr(getattr(result, "ineqlin", None), "marginals", None)
    if marginals is not None:
        dual = {f"square_{i}": float(max(0.0, -value)) for i, value in enumerate(marginals)}

    cert = {
        "schema": "unit_square_stab_certificate_v1",
        "problem": "unit_square",
        "squares": [json_point(square) for square in squares],
        "side": json_number(side),
        "critical_lines": lines,
        "incidence": incidence_lists,
        "tau_int": tau_int,
        "tau_lp": tau_lp,
        "score": score,
        "integer_lines": [lines[idx]["id"] for idx in chosen_lines],
        "lp_primal": {
            lines[i]["id"]: float(value) for i, value in enumerate(result.x) if abs(value) > 1e-10
        },
        "lp_dual": dual,
        "solver": {
            "integer_solver": "exact_branch_and_bound_set_cover",
            "lp_solver": "scipy.optimize.linprog",
            "lp_method": "highs",
            "tolerance": 1e-8,
        },
        "solver_status": "optimal",
        "exact_runtime_seconds": time.perf_counter() - start,
        "line_count": n_lines,
    }
    return attach_certificate_hash(cert)


def verify_certificate(cert: dict[str, Any], tolerance: float = 1e-8) -> bool:
    recomputed = score_instance({"squares": cert["squares"], "side": cert.get("side", 1)})
    return (
        cert.get("tau_int") == recomputed.get("tau_int")
        and abs(float(cert.get("tau_lp")) - float(recomputed.get("tau_lp"))) <= tolerance
        and abs(float(cert.get("score")) - float(recomputed.get("score"))) <= tolerance
    )
