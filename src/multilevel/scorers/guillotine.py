from __future__ import annotations

import functools
import itertools
import math
import time
from typing import Any

from multilevel.canonical import attach_certificate_hash
from multilevel.numbers import json_box, parse_box

Box = tuple[Any, Any, Any, Any]


def _validate_rectangles(raw: list[list[Any]]) -> list[Box]:
    rectangles = [parse_box(row) for row in raw]
    for rect in rectangles:
        x1, x2, y1, y2 = rect
        if not (x1 < x2 and y1 < y2):
            raise ValueError(f"invalid rectangle with nonpositive area: {rect!r}")
    for i, a in enumerate(rectangles):
        for j, b in enumerate(rectangles[i + 1 :], start=i + 1):
            if _interior_overlap(a, b):
                raise ValueError(f"rectangles {i} and {j} overlap in their interiors")
    return rectangles


def _interior_overlap(a: Box, b: Box) -> bool:
    ax1, ax2, ay1, ay2 = a
    bx1, bx2, by1, by2 = b
    return max(ax1, bx1) < min(ax2, bx2) and max(ay1, by1) < min(ay2, by2)


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def _popcount(mask: int) -> int:
    return bin(mask).count("1")


def _candidate_cut_coordinates(coords: list[Any]) -> list[Any]:
    """Coordinates at sides and one representative in every open side interval."""
    sides = sorted(set(coords))
    candidates = set(sides)
    for low, high in zip(sides, sides[1:]):
        if low < high:
            candidates.add((low + high) / 2)
    return sorted(candidates)


def _partition(rectangles: list[Box], mask: int, axis: str, coord) -> tuple[int, int, int]:
    low = 0
    high = 0
    crossed = 0
    for idx in _bits(mask):
        x1, x2, y1, y2 = rectangles[idx]
        bit = 1 << idx
        if axis == "x":
            if x1 < coord < x2:
                crossed |= bit
            elif x2 <= coord:
                low |= bit
            elif x1 >= coord:
                high |= bit
        else:
            if y1 < coord < y2:
                crossed |= bit
            elif y2 <= coord:
                low |= bit
            elif y1 >= coord:
                high |= bit
    return low, high, crossed


def _projection_components(rectangles: list[Box], mask: int, axis: str) -> list[int]:
    members = list(_bits(mask))
    if len(members) <= 1:
        return [mask] if mask else []
    intervals = []
    for idx in members:
        x1, x2, y1, y2 = rectangles[idx]
        intervals.append((idx, (x1, x2) if axis == "x" else (y1, y2)))
    parent = {idx: idx for idx in members}

    def find(idx: int) -> int:
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for left, (idx, interval) in enumerate(intervals):
        lo, hi = interval
        for other_idx, other in intervals[left + 1 :]:
            other_lo, other_hi = other
            if max(lo, other_lo) < min(hi, other_hi):
                union(idx, other_idx)
    components: dict[int, int] = {}
    for idx in members:
        root = find(idx)
        components[root] = components.get(root, 0) | (1 << idx)
    return list(components.values())


def _is_guillotine_separable_subset(rectangles: list[Box], mask: int) -> bool:
    @functools.lru_cache(maxsize=None)
    def solve(state: int) -> bool:
        if _popcount(state) <= 1:
            return True
        for axis in ("x", "y"):
            components = _projection_components(rectangles, state, axis)
            if len(components) > 1 and all(solve(component) for component in components):
                return True
        return False

    return solve(mask)


def _subset_mask(combo: tuple[int, ...]) -> int:
    mask = 0
    for idx in combo:
        mask |= 1 << idx
    return mask


def _sample_subset_masks(n: int, k: int, limit: int) -> list[int]:
    if limit <= 0:
        return []
    masks: list[int] = []
    seen: set[int] = set()

    def add(mask: int) -> None:
        if mask not in seen and len(masks) < limit:
            seen.add(mask)
            masks.append(mask)

    for start in range(min(n, limit)):
        add(sum(1 << ((start + offset) % n) for offset in range(k)))
    for stride in range(1, n):
        for start in range(n):
            combo = sorted({(start + stride * offset) % n for offset in range(k)})
            if len(combo) == k:
                add(_subset_mask(tuple(combo)))
            if len(masks) >= limit:
                return masks
    for combo in itertools.combinations(range(n), k):
        add(_subset_mask(combo))
        if len(masks) >= limit:
            return masks
    return masks


def _k_subset_nonseparability_summary(
    rectangles: list[Box],
    *,
    exact_max_n: int = 16,
    sample_limit: int = 1024,
) -> dict[str, Any]:
    n = len(rectangles)
    k = n // 2 + 1
    if n == 0:
        return {
            "threshold_k": 0,
            "threshold_exact": True,
            "threshold_total_checked": 0,
            "threshold_separable_count": 0,
            "threshold_nonseparable_fraction": 1.0,
            "threshold_target_met": True,
            "threshold_witness_mask": 0,
            "threshold_witness_indices": [],
        }
    total_exact = math.comb(n, k)
    exact = n <= exact_max_n
    if exact:
        masks = [_subset_mask(combo) for combo in itertools.combinations(range(n), k)]
        total_candidates = total_exact
    else:
        masks = _sample_subset_masks(n, k, min(sample_limit, total_exact))
        total_candidates = len(masks)
    separable = 0
    witness = 0
    for mask in masks:
        if _is_guillotine_separable_subset(rectangles, mask):
            separable += 1
            if witness == 0:
                witness = mask
    checked = len(masks)
    nonseparable_fraction = 1.0 - separable / max(1, checked)
    return {
        "threshold_k": k,
        "threshold_exact": exact,
        "threshold_total_k_subsets": total_candidates,
        "threshold_total_checked": checked,
        "threshold_separable_count": separable,
        "threshold_nonseparable_fraction": nonseparable_fraction,
        "threshold_target_met": separable == 0,
        "threshold_witness_mask": witness,
        "threshold_witness_indices": list(_bits(witness)) if witness else [],
    }


def k_subset_nonseparability_summary(
    instance: dict[str, Any],
    *,
    exact_max_n: int = 16,
    sample_limit: int = 1024,
) -> dict[str, Any]:
    rectangles = _validate_rectangles(instance["rectangles"])
    return _k_subset_nonseparability_summary(rectangles, exact_max_n=exact_max_n, sample_limit=sample_limit)


def score_instance(instance: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    rectangles = _validate_rectangles(instance["rectangles"])
    n = len(rectangles)
    if n == 0:
        raise ValueError("guillotine instance must contain at least one rectangle")
    x_coords = sorted({coord for x1, x2, _, _ in rectangles for coord in (x1, x2)})
    y_coords = sorted({coord for _, _, y1, y2 in rectangles for coord in (y1, y2)})
    x_cuts = _candidate_cut_coordinates(x_coords)
    y_cuts = _candidate_cut_coordinates(y_coords)
    state_count = 0

    @functools.lru_cache(maxsize=None)
    def solve(mask: int) -> tuple[int, dict[str, Any]]:
        nonlocal state_count
        state_count += 1
        members = list(_bits(mask))
        if len(members) <= 1:
            return len(members), {"type": "leaf", "rectangles": members}

        best_saved = -1
        best_strategy: dict[str, Any] | None = None
        for axis, coords in (("x", x_cuts), ("y", y_cuts)):
            for coord in coords:
                low, high, crossed = _partition(rectangles, mask, axis, coord)
                if crossed == 0 and (low == mask or high == mask):
                    continue
                if (low | high | crossed) != mask:
                    continue
                low_saved, low_strategy = solve(low)
                high_saved, high_strategy = solve(high)
                saved = low_saved + high_saved
                if saved > best_saved:
                    best_saved = saved
                    best_strategy = {
                        "type": "cut",
                        "axis": "vertical" if axis == "x" else "horizontal",
                        "coordinate": str(coord),
                        "destroyed": list(_bits(crossed)),
                        "low": low_strategy,
                        "high": high_strategy,
                    }
        if best_strategy is None:
            # Degenerate fallback: keep one rectangle when no progressing cut was
            # generated. This should not occur for ordinary disjoint layouts, but
            # keeping the result structured is better than silently looping.
            first = members[0]
            return 1, {"type": "fallback_leaf", "rectangles": [first]}
        return best_saved, best_strategy

    full_mask = (1 << n) - 1
    saved, strategy = solve(full_mask)
    threshold_summary = _k_subset_nonseparability_summary(
        rectangles,
        exact_max_n=14,
        sample_limit=256,
    )
    first_cut_crossed = n
    for axis, coords in (("x", x_cuts), ("y", y_cuts)):
        for coord in coords:
            low, high, crossed = _partition(rectangles, full_mask, axis, coord)
            if crossed == 0 and (low == full_mask or high == full_mask):
                continue
            if (low | high | crossed) == full_mask:
                first_cut_crossed = min(first_cut_crossed, _popcount(crossed))
    destroyed = n - saved
    score = destroyed / n
    cert = {
        "schema": "guillotine_certificate_v1",
        "problem": "guillotine",
        "rectangles": [json_box(rect) for rect in rectangles],
        "n": n,
        "saved": saved,
        "destroyed": destroyed,
        "score": score,
        "first_cut_destroyed_fraction": first_cut_crossed / n,
        **threshold_summary,
        "dp_states": state_count,
        "optimal_strategy": strategy,
        "solver": {
            "solver": "exact_recursive_guillotine_dynamic_program",
            "state_key": "rectangle_subset_bitmask",
            "cache": "functools.lru_cache",
            "cut_coordinates": "rectangle_boundaries_and_open_interval_midpoints",
            "tolerance": 0.0,
        },
        "solver_status": "optimal",
        "exact_runtime_seconds": time.perf_counter() - start,
    }
    return attach_certificate_hash(cert)


def verify_certificate(cert: dict[str, Any], tolerance: float = 1e-8) -> bool:
    recomputed = score_instance({"rectangles": cert["rectangles"]})
    return (
        cert.get("saved") == recomputed.get("saved")
        and cert.get("destroyed") == recomputed.get("destroyed")
        and abs(float(cert.get("score")) - float(recomputed.get("score"))) <= tolerance
    )
