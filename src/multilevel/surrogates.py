from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from multilevel.scorers import guillotine, misr, unit_square


def surrogate_score(problem: str, surrogate: str, instance: dict[str, Any]) -> dict[str, Any]:
    if problem == "misr":
        return misr_surrogate(surrogate, instance)
    if problem == "unit_square":
        return unit_square_surrogate(surrogate, instance)
    if problem == "guillotine":
        return guillotine_surrogate(surrogate, instance)
    raise ValueError(f"unknown problem: {problem}")


def misr_surrogate(surrogate: str, instance: dict[str, Any]) -> dict[str, Any]:
    rectangles = misr._validate_rectangles(instance["rectangles"])
    adj = misr._intersection_graph(rectangles)
    triangle_free = misr._is_triangle_free(adj)
    n = len(rectangles)
    edges = sum(bin(mask).count("1") for mask in adj) // 2
    edge_density = edges / max(1, n * (n - 1) / 2)
    alpha_hint: int | None = None
    cliques: list[list[int]] | None = None

    def get_alpha_hint() -> int:
        nonlocal alpha_hint
        if alpha_hint is None:
            alpha_hint = max(1, len(misr._maximum_independent_set(adj)))
        return alpha_hint

    def get_cliques() -> list[list[int]]:
        nonlocal cliques
        if cliques is None:
            cliques = misr._maximal_cliques(adj)
        return cliques

    def get_max_clique() -> int:
        return max((len(c) for c in get_cliques()), default=1)

    def get_clique_pressure() -> float:
        rows = get_cliques()
        return mean(len(c) for c in rows) if rows else 1.0

    if surrogate == "greedy_sampled_clique_lp":
        alpha = get_alpha_hint()
        score = (n / alpha) * (1.0 + 0.15 * edge_density)
    elif surrogate == "graph_conflict_proxy":
        alpha = get_alpha_hint()
        max_clique = get_max_clique()
        score = edge_density * n / alpha + 0.05 * max_clique
        if triangle_free:
            score += 0.1 * (n / (2.0 * alpha))
    elif surrogate == "dual_packing_compression":
        alpha = get_alpha_hint()
        rows = get_cliques()
        clique_pressure = get_clique_pressure()
        score = clique_pressure / alpha + math.log1p(len(rows)) / max(1, n)
    elif surrogate == "triangle_free_exact_gap_pressure":
        if not triangle_free:
            score = -1_000_000.0 + edge_density
            return {
                "surrogate_score": score,
                "features": {
                    "n": n,
                    "edges": edges,
                    "edge_density": edge_density,
                    "alpha_hint": None,
                    "max_clique": 3,
                    "triangle_free": triangle_free,
                    "maximal_cliques": None,
                    "clique_pressure": None,
                    "rejected_reason": "triangle_detected",
                },
            }
        constrained = {**instance, "constraints": {"triangle_free": True}}
        cert = misr.score_instance(constrained)
        score = float(cert["score"])
        alpha_int = int(cert["alpha_int"])
        alpha_lp = float(cert["alpha_lp"])
        certified_lower_bound = n / (2.0 * max(1, alpha_int))
        score += 0.02 * certified_lower_bound + 0.002 * edges / max(1, n)
        return {
            "surrogate_score": score,
            "features": {
                "n": n,
                "edges": edges,
                "edge_density": edge_density,
                "alpha_hint": alpha_int,
                "alpha_int": alpha_int,
                "alpha_lp": alpha_lp,
                "triangle_free_certified_lower_bound": certified_lower_bound,
                "max_clique": cert.get("max_clique_size"),
                "triangle_free": triangle_free,
                "maximal_cliques": cert.get("maximal_cliques"),
                "clique_pressure": None,
                "exact_runtime_seconds": cert.get("exact_runtime_seconds"),
            },
        }
    elif surrogate == "exact_lp_gap_pressure":
        cert = misr.score_instance(instance)
        score = float(cert["score"])
        alpha_int = int(cert["alpha_int"])
        alpha_lp = float(cert["alpha_lp"])
        certified_lower_bound = n / (2.0 * max(1, alpha_int)) if triangle_free else None
        if certified_lower_bound is not None:
            score += 0.01 * certified_lower_bound
        return {
            "surrogate_score": score,
            "features": {
                "n": n,
                "edges": edges,
                "edge_density": edge_density,
                "alpha_hint": alpha_int,
                "alpha_int": alpha_int,
                "alpha_lp": alpha_lp,
                "triangle_free_certified_lower_bound": certified_lower_bound,
                "max_clique": cert.get("max_clique_size"),
                "triangle_free": triangle_free,
                "maximal_cliques": cert.get("maximal_cliques"),
                "clique_pressure": None,
                "exact_runtime_seconds": cert.get("exact_runtime_seconds"),
            },
        }
    else:
        raise ValueError(f"unknown MISR surrogate: {surrogate}")
    return {
        "surrogate_score": score,
        "features": {
            "n": n,
            "edges": edges,
            "edge_density": edge_density,
            "alpha_hint": get_alpha_hint(),
            "max_clique": get_max_clique(),
            "triangle_free": triangle_free,
            "maximal_cliques": len(get_cliques()),
            "clique_pressure": get_clique_pressure(),
        },
    }


def unit_square_surrogate(surrogate: str, instance: dict[str, Any]) -> dict[str, Any]:
    squares = [unit_square.parse_point(row) for row in instance["squares"]]
    side = unit_square.parse_number(instance.get("side", 1))
    lines, masks = unit_square._line_universe(squares, side=side)
    n = len(squares)
    all_squares = (1 << n) - 1
    greedy = len(unit_square._greedy_cover(masks, all_squares))
    frequencies = [bin(mask).count("1") for mask in masks]
    max_freq = max(frequencies, default=1)
    avg_freq = mean(frequencies) if frequencies else 0.0
    freq_std = pstdev(frequencies) if len(frequencies) > 1 else 0.0
    fractional_lower = max(1.0, n / max_freq)

    if surrogate == "greedy_partial_lp_bitset":
        score = greedy / fractional_lower
    elif surrogate == "incidence_statistics":
        balance = 1.0 / (1.0 + freq_std)
        score = greedy * balance + 0.02 * len(lines)
    elif surrogate == "threshold_rounding_loss":
        score = greedy / max(1.0, avg_freq) + 0.05 * freq_std
    elif surrogate == "exact_stab_gap_pressure":
        cert = unit_square.score_instance(instance)
        tau_int = float(cert.get("tau_int") or 0.0)
        tau_lp = float(cert.get("tau_lp") or 1.0)
        lp_support = len(cert.get("lp_primal") or {})
        score = (
            float(cert["score"])
            + 0.015 * tau_int
            - 0.004 * tau_lp
            + 0.002 * min(lp_support, 12)
        )
        return {
            "surrogate_score": score,
            "features": {
                "n": n,
                "side": str(side),
                "line_count": len(lines),
                "greedy_cover": greedy,
                "tau_int": cert.get("tau_int"),
                "tau_lp": cert.get("tau_lp"),
                "exact_score": cert.get("score"),
                "lp_support": lp_support,
                "max_line_frequency": max_freq,
                "avg_line_frequency": avg_freq,
                "line_frequency_std": freq_std,
                "fractional_lower_hint": fractional_lower,
                "exact_runtime_seconds": cert.get("exact_runtime_seconds"),
            },
        }
    else:
        raise ValueError(f"unknown unit-square surrogate: {surrogate}")
    return {
        "surrogate_score": score,
        "features": {
            "n": n,
            "side": str(side),
            "line_count": len(lines),
            "greedy_cover": greedy,
            "max_line_frequency": max_freq,
            "avg_line_frequency": avg_freq,
            "line_frequency_std": freq_std,
            "fractional_lower_hint": fractional_lower,
        },
    }


def guillotine_surrogate(surrogate: str, instance: dict[str, Any]) -> dict[str, Any]:
    rectangles = guillotine._validate_rectangles(instance["rectangles"])
    n = len(rectangles)
    full_mask = (1 << n) - 1
    x_coords = sorted({coord for x1, x2, _, _ in rectangles for coord in (x1, x2)})
    y_coords = sorted({coord for _, _, y1, y2 in rectangles for coord in (y1, y2)})
    x_cuts = guillotine._candidate_cut_coordinates(x_coords)
    y_cuts = guillotine._candidate_cut_coordinates(y_coords)
    cuts = []
    for axis, coords in (("x", x_cuts), ("y", y_cuts)):
        for coord in coords:
            low, high, crossed = guillotine._partition(rectangles, full_mask, axis, coord)
            if crossed == 0 and (low == full_mask or high == full_mask):
                continue
            if (low | high | crossed) == full_mask:
                cuts.append((axis, coord, bin(crossed).count("1"), bin(low).count("1"), bin(high).count("1")))
    min_crossed = min((row[2] for row in cuts), default=0)
    balanced = [
        row[2]
        for row in cuts
        if row[3] > 0 and row[4] > 0 and min(row[3], row[4]) / max(row[3], row[4]) >= 0.35
    ]
    balanced_min = min(balanced, default=min_crossed)
    x_span = _projection_span([(r[0], r[1]) for r in rectangles])
    y_span = _projection_span([(r[2], r[3]) for r in rectangles])
    entropy_hint = min(x_span, y_span) / max(x_span, y_span, 1e-9)

    if surrogate == "first_cut_obstruction":
        score = min_crossed / max(1, n)
    elif surrogate == "depth_limited_dp":
        depth_saved = _depth_limited_guillotine_saved(rectangles, full_mask, x_cuts, y_cuts, depth=3)
        depth_destroyed_fraction = 1.0 - depth_saved / max(1, n)
        score = depth_destroyed_fraction + 0.05 * (balanced_min / max(1, n)) + 0.02 * entropy_hint
    elif surrogate == "projection_overlap_entropy":
        score = entropy_hint + 0.25 * min_crossed / max(1, n)
    elif surrogate == "k_subset_nonseparability":
        threshold = guillotine._k_subset_nonseparability_summary(
            rectangles,
            exact_max_n=16,
            sample_limit=2048,
        )
        depth_saved = None
        depth_destroyed_fraction = None
        score = (
            float(threshold["threshold_nonseparable_fraction"])
            + 0.10 * (balanced_min / max(1, n))
            + 0.02 * entropy_hint
            + 0.02 * (n / max(1, n + 10))
            + (0.25 if threshold["threshold_target_met"] else 0.0)
        )
    elif surrogate == "exact_recursive_dp":
        cert = guillotine.score_instance(instance)
        score = float(cert["score"])
        depth_saved = cert.get("saved")
        depth_destroyed_fraction = score
    else:
        raise ValueError(f"unknown guillotine surrogate: {surrogate}")
    if surrogate != "depth_limited_dp" and surrogate != "exact_recursive_dp":
        depth_saved = None
        depth_destroyed_fraction = None
    return {
        "surrogate_score": score,
        "features": {
            "n": n,
            "candidate_cuts": len(cuts),
            "min_first_cut_crossed": min_crossed,
            "balanced_min_first_cut_crossed": balanced_min,
            "depth_limited_saved": depth_saved,
            "depth_limited_destroyed_fraction": depth_destroyed_fraction,
            "x_projection_span": x_span,
            "y_projection_span": y_span,
            "projection_entropy_hint": entropy_hint,
            **(threshold if surrogate == "k_subset_nonseparability" else {}),
        },
    }


def _depth_limited_guillotine_saved(rectangles, full_mask: int, x_cuts, y_cuts, *, depth: int) -> int:
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def solve(mask: int, remaining_depth: int) -> int:
        members = guillotine._popcount(mask)
        if members <= 1:
            return members
        if remaining_depth <= 0:
            return members
        best = -1
        for axis, coords in (("x", x_cuts), ("y", y_cuts)):
            for coord in coords:
                low, high, crossed = guillotine._partition(rectangles, mask, axis, coord)
                if crossed == 0 and (low == mask or high == mask):
                    continue
                if (low | high | crossed) != mask:
                    continue
                saved = solve(low, remaining_depth - 1) + solve(high, remaining_depth - 1)
                if saved > best:
                    best = saved
        return 1 if best < 0 else best

    return solve(full_mask, depth)


def _projection_span(intervals) -> float:
    if not intervals:
        return 0.0
    return float(max(hi for _, hi in intervals) - min(lo for lo, _ in intervals))
