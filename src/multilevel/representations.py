from __future__ import annotations

import random
import math
from typing import Any

from multilevel import misr_sequences
from multilevel.random_instances import GENERATORS


DEFAULT_REPRESENTATION = {
    "misr": "endpoint_sequence_pair",
    "unit_square": "square_direct",
    "guillotine": "rect_direct_disjoint",
}


_MISR_PROGRAM_DECODERS = ("endpoints", "center_size", "thin_segments")


def initial_instance_for_representation(
    problem: str,
    representation: str,
    rng: random.Random,
    *,
    n: int,
    grid: int,
) -> dict[str, Any]:
    if problem == "misr":
        return _misr_instance(representation, rng, n=n, grid=grid)
    if problem == "unit_square":
        return _unit_square_instance(representation, rng, n=n, grid=grid)
    if problem == "guillotine":
        return _guillotine_instance(representation, rng, n=n, grid=grid)
    return GENERATORS[problem](rng, n=n, grid=grid)


def default_representation(problem: str) -> str:
    if problem not in DEFAULT_REPRESENTATION:
        raise ValueError(f"no default representation for problem: {problem}")
    return DEFAULT_REPRESENTATION[problem]


def decoded_geometry(instance: dict[str, Any]) -> dict[str, Any]:
    """Return the solver-facing geometry, dropping search metadata."""
    return {key: value for key, value in instance.items() if not key.startswith("_")}


def repair_instance_for_representation(
    problem: str,
    representation: str | None,
    instance: dict[str, Any],
    *,
    grid: int,
    n_min: int = 1,
    n_max: int = 128,
) -> dict[str, Any]:
    """Clamp decoded geometry and refresh representation payload metadata.

    The registered representations are decoded to ordinary scorer inputs. This
    function keeps those decoded inputs valid after local or model mutations
    while preserving enough representation metadata for search/audit logs.
    """
    rep = representation or str(instance.get("_representation") or default_representation(problem))
    if problem == "misr":
        return _repair_misr(rep, instance, grid=grid, n_min=n_min, n_max=n_max)
    if problem == "unit_square":
        return _repair_unit_square(rep, instance, grid=grid, n_min=n_min, n_max=n_max)
    if problem == "guillotine":
        return _repair_guillotine(rep, instance, grid=grid, n_min=n_min, n_max=n_max)
    return decoded_geometry(instance)


def _tag(instance: dict[str, Any], representation: str, payload: dict[str, Any]) -> dict[str, Any]:
    instance["_representation"] = representation
    instance["_representation_payload"] = payload
    return instance


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return default


def _fixed_representation_target(instance: dict[str, Any], *, n_min: int, n_max: int) -> int:
    payload = instance.get("_representation_payload", {})
    raw_target = payload.get("target_n", n_min) if isinstance(payload, dict) else n_min
    return max(n_min, min(n_max, _to_int(raw_target, n_min)))


def _canonicalize_d4_squares(squares: list[list[int]]) -> list[list[int]]:
    """Canonicalize square positions under translation and all eight D4 symmetries."""
    if not squares:
        return []
    forms: list[tuple[tuple[int, int], ...]] = []
    for swap_axes in (False, True):
        for x_sign in (-1, 1):
            for y_sign in (-1, 1):
                transformed = []
                for x, y in squares:
                    a, b = (y, x) if swap_axes else (x, y)
                    transformed.append((x_sign * a, y_sign * b))
                min_x = min(x for x, _ in transformed)
                min_y = min(y for _, y in transformed)
                forms.append(tuple(sorted({(x - min_x, y - min_y) for x, y in transformed})))
    return [list(point) for point in min(forms)]


def _canonicalize_d4_rectangles(rectangles: list[list[int]]) -> list[list[int]]:
    """Canonicalize axis-parallel rectangles under translation and D4 symmetries."""
    if not rectangles:
        return []
    forms: list[tuple[tuple[int, int, int, int], ...]] = []
    for swap_axes in (False, True):
        for x_sign in (-1, 1):
            for y_sign in (-1, 1):
                transformed: list[tuple[int, int, int, int]] = []
                for x1, x2, y1, y2 in rectangles:
                    x_interval = (y1, y2) if swap_axes else (x1, x2)
                    y_interval = (x1, x2) if swap_axes else (y1, y2)
                    tx1, tx2 = x_interval if x_sign > 0 else (-x_interval[1], -x_interval[0])
                    ty1, ty2 = y_interval if y_sign > 0 else (-y_interval[1], -y_interval[0])
                    transformed.append((tx1, tx2, ty1, ty2))
                min_x = min(rect[0] for rect in transformed)
                min_y = min(rect[2] for rect in transformed)
                forms.append(
                    tuple(
                        sorted(
                            (x1 - min_x, x2 - min_x, y1 - min_y, y2 - min_y)
                            for x1, x2, y1, y2 in transformed
                        )
                    )
                )
    return [list(rectangle) for rectangle in min(forms)]


def _clean_rectangles(raw: Any, *, grid: int, n_min: int, n_max: int) -> list[list[int]]:
    if not isinstance(raw, list):
        raw = []
    rects: list[list[int]] = []
    upper_lo = max(0, grid + 1)
    upper_hi = max(1, grid + 2)
    for row in raw[: max(0, n_max)]:
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            continue
        x1 = max(0, min(upper_lo, _to_int(row[0])))
        x2 = max(1, min(upper_hi, _to_int(row[1], x1 + 1)))
        y1 = max(0, min(upper_lo, _to_int(row[2])))
        y2 = max(1, min(upper_hi, _to_int(row[3], y1 + 1)))
        if x2 <= x1:
            x2 = min(upper_hi, x1 + 1)
            x1 = min(x1, x2 - 1)
        if y2 <= y1:
            y2 = min(upper_hi, y1 + 1)
            y1 = min(y1, y2 - 1)
        rects.append([x1, x2, y1, y2])
    while len(rects) < n_min:
        offset = len(rects) % max(1, grid + 1)
        rects.append([offset, offset + 1, 0, 1])
    return rects


def _clean_squares(raw: Any, *, grid: int, n_min: int, n_max: int) -> list[list[int]]:
    if not isinstance(raw, list):
        raw = []
    squares: list[list[int]] = []
    for row in raw[: max(0, n_max)]:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        x = max(0, min(grid, _to_int(row[0])))
        y = max(0, min(grid, _to_int(row[1])))
        squares.append([x, y])
    while len(squares) < n_min:
        offset = len(squares) % max(1, grid + 1)
        squares.append([offset, offset])
    return squares


def _rect_intersects(a: list[int], b: list[int]) -> bool:
    return max(a[0], b[0]) <= min(a[1], b[1]) and max(a[2], b[2]) <= min(a[3], b[3])


def _intersection_masks(rects: list[list[int]]) -> list[int]:
    adj = [0] * len(rects)
    for i, rect in enumerate(rects):
        for j in range(i + 1, len(rects)):
            if _rect_intersects(rect, rects[j]):
                adj[i] |= 1 << j
                adj[j] |= 1 << i
    return adj


def _popcount(mask: int) -> int:
    return bin(mask).count("1")


def _color_sort(candidates: int, adj: list[int]) -> tuple[list[int], list[int]]:
    order: list[int] = []
    bounds: list[int] = []
    remaining = candidates
    color = 0
    while remaining:
        color += 1
        available = remaining
        while available:
            bit = available & -available
            vertex = bit.bit_length() - 1
            order.append(vertex)
            bounds.append(color)
            remaining &= ~bit
            available &= ~bit
            available &= ~adj[vertex]
    return order, bounds


def _maximum_clique_size(adj: list[int]) -> int:
    best = 0

    def expand(size: int, candidates: int) -> None:
        nonlocal best
        if not candidates:
            best = max(best, size)
            return
        order, bounds = _color_sort(candidates, adj)
        for idx in range(len(order) - 1, -1, -1):
            vertex = order[idx]
            if size + bounds[idx] <= best:
                return
            bit = 1 << vertex
            if not (candidates & bit):
                continue
            expand(size + 1, candidates & adj[vertex])
            candidates &= ~bit

    expand(0, (1 << len(adj)) - 1)
    return best


def _maximum_independent_set_size(adj: list[int]) -> int:
    n = len(adj)
    all_mask = (1 << n) - 1
    complement = [all_mask & ~(1 << idx) & ~adj[idx] for idx in range(n)]
    return _maximum_clique_size(complement)


def _triangle_witness(rects: list[list[int]]) -> tuple[int, int, int] | None:
    adj = _intersection_masks(rects)
    for i in range(len(adj)):
        for j in range(i + 1, len(adj)):
            if not (adj[i] & (1 << j)):
                continue
            common = adj[i] & adj[j] & ~((1 << (j + 1)) - 1)
            if common:
                k = (common & -common).bit_length() - 1
                return i, j, k
    return None


def _triangles(rects: list[list[int]]) -> list[tuple[int, int, int]]:
    adj = _intersection_masks(rects)
    out: list[tuple[int, int, int]] = []
    for i in range(len(adj)):
        for j in range(i + 1, len(adj)):
            if not (adj[i] & (1 << j)):
                continue
            common = adj[i] & adj[j] & ~((1 << (j + 1)) - 1)
            while common:
                bit = common & -common
                out.append((i, j, bit.bit_length() - 1))
                common ^= bit
    return out


def _is_triangle_free_rectangles(rects: list[list[int]]) -> bool:
    return _triangle_witness(rects) is None


def _triangle_free_payload(rects: list[list[int]]) -> dict[str, Any]:
    adj = _intersection_masks(rects)
    edge_count = sum(_popcount(mask) for mask in adj) // 2
    alpha = _maximum_independent_set_size(adj) if rects else 0
    return {
        "generator": "triangle_free_rectangles",
        "triangle_free": _is_triangle_free_rectangles(rects),
        "edge_count": edge_count,
        "max_degree": max((_popcount(mask) for mask in adj), default=0),
        "alpha_int": alpha,
        "certified_lower_bound": (len(rects) / (2.0 * alpha)) if alpha else 0.0,
    }


def _triangle_free_key(rects: list[list[int]]) -> tuple[float, int, int, int, int]:
    if not rects:
        return (0.0, 0, 0, 0, 0)
    adj = _intersection_masks(rects)
    alpha = max(1, _maximum_independent_set_size(adj))
    edges = sum(_popcount(mask) for mask in adj) // 2
    degrees = [_popcount(mask) for mask in adj]
    return (len(rects) / (2.0 * alpha), -alpha, edges, min(degrees, default=0), len(rects))


def _triangle_free_subset(
    rects: list[list[int]],
    *,
    grid: int,
    n_min: int,
    n_max: int | None = None,
    rng: random.Random | None = None,
) -> list[list[int]]:
    rects = [list(rect) for rect in rects]
    while True:
        witness = _triangle_witness(rects)
        if witness is None:
            break
        participation = [0] * len(rects)
        for triangle in _triangles(rects):
            for idx in triangle:
                participation[idx] += 1
        if rng is None:
            drop = max(
                witness,
                key=lambda idx: (
                    _triangle_free_key(rects[:idx] + rects[idx + 1 :]),
                    participation[idx],
                    tuple(rects[idx]),
                    -idx,
                ),
            )
        else:
            drop = max(
                witness,
                key=lambda idx: (
                    _triangle_free_key(rects[:idx] + rects[idx + 1 :]),
                    participation[idx],
                    rng.random(),
                ),
            )
        del rects[drop]
    rects = _fill_triangle_free_dense(rects, rng, target_size=n_min, grid=grid)
    if n_max is not None and len(rects) > n_max:
        rects = _trim_triangle_free(rects, n_max, rng)
    return rects


def _triangle_free_candidate_pool(
    rects: list[list[int]],
    rng: random.Random,
    *,
    grid: int,
    count: int,
) -> list[list[int]]:
    side = max(4, grid + 2)
    pool: list[list[int]] = []
    for _ in range(count):
        mode = rng.randrange(100)
        if rects and mode < 45:
            base = rng.choice(rects)
            span_x = max(2, base[1] - base[0] + 2)
            span_y = max(2, base[3] - base[2] + 2)
            x1 = max(0, min(side - 1, base[0] + rng.randrange(-span_x, span_x + 1)))
            y1 = max(0, min(side - 1, base[2] + rng.randrange(-span_y, span_y + 1)))
            width = rng.randrange(1, min(side - x1, span_x + 2) + 1)
            height = rng.randrange(1, min(side - y1, span_y + 2) + 1)
            pool.append([x1, x1 + width, y1, y1 + height])
        elif mode < 70:
            width = rng.randrange(1, max(2, min(3, side) + 1))
            height = rng.randrange(max(1, side // 3), side + 1)
            x1 = rng.randrange(0, max(1, side - width + 1))
            y1 = rng.randrange(0, max(1, side - height + 1))
            pool.append([x1, x1 + width, y1, y1 + height])
        elif mode < 95:
            width = rng.randrange(max(1, side // 3), side + 1)
            height = rng.randrange(1, max(2, min(3, side) + 1))
            x1 = rng.randrange(0, max(1, side - width + 1))
            y1 = rng.randrange(0, max(1, side - height + 1))
            pool.append([x1, x1 + width, y1, y1 + height])
        else:
            pool.append(_random_rect(rng, grid=grid))
    return pool


def _triangle_free_deterministic_candidate_pool(rects: list[list[int]], *, grid: int) -> list[list[int]]:
    side = max(4, grid + 2)
    seen: set[tuple[int, int, int, int]] = set()
    pool: list[list[int]] = []

    def add(rect: list[int]) -> None:
        if rect[0] >= rect[1] or rect[2] >= rect[3]:
            return
        key = tuple(rect)
        if key in seen:
            return
        seen.add(key)
        pool.append(rect)

    for rect in rects:
        x1, x2, y1, y2 = rect
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            nx = max(0, min(side - width, x1 + dx))
            ny = max(0, min(side - height, y1 + dy))
            add([nx, nx + width, ny, ny + height])
            add([nx, min(side, nx + 1), 0, side])
            add([0, side, ny, min(side, ny + 1)])

    for x in range(side):
        add([x, x + 1, 0, side])
    for y in range(side):
        add([0, side, y, y + 1])
    for x in range(side):
        for y in range(side):
            add([x, x + 1, y, y + 1])
    return pool


def _can_add_triangle_free(rects: list[list[int]], candidate: list[int]) -> bool:
    if candidate[0] >= candidate[1] or candidate[2] >= candidate[3]:
        return False
    adj = _intersection_masks(rects)
    neighbors = 0
    for idx, rect in enumerate(rects):
        if _rect_intersects(candidate, rect):
            neighbors |= 1 << idx
    while neighbors:
        bit = neighbors & -neighbors
        idx = bit.bit_length() - 1
        if adj[idx] & (neighbors ^ bit):
            return False
        neighbors ^= bit
    return True


def _fill_triangle_free_dense(
    rects: list[list[int]],
    rng: random.Random | None,
    *,
    target_size: int,
    grid: int,
) -> list[list[int]]:
    out = [list(rect) for rect in rects]
    target_size = max(0, target_size)
    while len(out) < target_size:
        best: list[int] | None = None
        best_key: tuple[Any, ...] | None = None
        if rng is None:
            pool = _triangle_free_deterministic_candidate_pool(out, grid=grid)
        else:
            pool = _triangle_free_candidate_pool(
                out,
                rng,
                grid=grid,
                count=max(96, 16 * max(1, target_size)),
            )
        for candidate in pool:
            if not _can_add_triangle_free(out, candidate):
                continue
            if rng is None:
                key = (*_triangle_free_key(out + [candidate]), tuple(candidate))
            else:
                key = (*_triangle_free_key(out + [candidate]), rng.random())
            if best_key is None or key > best_key:
                best_key = key
                best = candidate
        if best is None:
            side = max(4, grid + 2)
            cursor = len(out)
            while True:
                candidate = [(2 * cursor) % side, (2 * cursor) % side + 1, side + cursor, side + cursor + 1]
                cursor += 1
                if _can_add_triangle_free(out, candidate):
                    best = candidate
                    break
        out.append(best)
    return out


def _trim_triangle_free(rects: list[list[int]], max_size: int, rng: random.Random | None) -> list[list[int]]:
    out = [list(rect) for rect in rects]
    while len(out) > max_size:
        if rng is None:
            drop = max(
                range(len(out)),
                key=lambda idx: (*_triangle_free_key(out[:idx] + out[idx + 1 :]), tuple(out[idx]), -idx),
            )
        else:
            drop = max(
                range(len(out)),
                key=lambda idx: (*_triangle_free_key(out[:idx] + out[idx + 1 :]), rng.random()),
            )
        del out[drop]
    return out


def _random_rect(rng: random.Random, *, grid: int) -> list[int]:
    side = max(2, grid + 2)
    x1 = rng.randrange(0, side)
    y1 = rng.randrange(0, side)
    x2 = rng.randrange(x1 + 1, side + 1)
    y2 = rng.randrange(y1 + 1, side + 1)
    return [x1, x2, y1, y2]


def _isolated_rect(index: int, *, grid: int) -> list[int]:
    side = max(2, grid + 2)
    slots_per_row = max(1, (side + 1) // 2)
    x = 2 * (index % slots_per_row)
    y = 2 * (index // slots_per_row)
    return [x, x + 1, y, y + 1]


def _interior_overlap(a: list[int], b: list[int]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1]) and max(a[2], b[2]) < min(a[3], b[3])


def _payload_layers(instance: dict[str, Any], fallback: int) -> int:
    payload = instance.get("_representation_payload", {})
    if isinstance(payload, dict):
        raw = payload.get("layers", fallback)
        return max(1, _to_int(raw, fallback))
    return fallback


def _program_feature_count(t: int) -> int:
    return 1 + t + t * (t + 1) // 2


def _program_bits(index: int, t: int) -> list[int]:
    return [(index >> bit) & 1 for bit in range(t)]


def _program_features(index: int, t: int) -> list[int]:
    bits = _program_bits(index, t)
    features = [1]
    features.extend(bits)
    for i in range(t):
        for j in range(i, t):
            features.append(bits[i] * bits[j])
    return features


def _program_value(coeffs: list[int], index: int, t: int, modulus: int) -> int:
    features = _program_features(index, t)
    total = sum(c * f for c, f in zip(coeffs, features))
    return total % max(1, modulus)


def _default_program_coeffs(name: str, feature_count: int, bound: int) -> list[int]:
    salt = sum(ord(ch) for ch in name)
    span = 2 * bound + 1
    return [((salt + 17 * idx + 5 * idx * idx) % span) - bound for idx in range(feature_count)]


def _clean_program_coeffs(raw: Any, name: str, feature_count: int, bound: int) -> list[int]:
    if not isinstance(raw, list):
        return _default_program_coeffs(name, feature_count, bound)
    coeffs = [
        max(-bound, min(bound, _to_int(value)))
        for value in raw[:feature_count]
    ]
    if len(coeffs) < feature_count:
        coeffs.extend(_default_program_coeffs(name, feature_count - len(coeffs), bound))
    return coeffs


def _random_program_coeffs(rng: random.Random, feature_count: int, bound: int) -> dict[str, list[int]]:
    return {
        name: [rng.randrange(-bound, bound + 1) for _ in range(feature_count)]
        for name in ("a", "b", "c", "d")
    }


def _random_composition(rng: random.Random, total: int, parts: int) -> list[int]:
    parts = max(1, min(parts, total))
    remaining = total
    composition: list[int] = []
    for idx in range(parts):
        slots_left = parts - idx - 1
        if slots_left == 0:
            value = remaining
        else:
            value = rng.randrange(1, remaining - slots_left + 1)
        composition.append(value)
        remaining -= value
    return composition


def _clean_composition(raw: Any, total: int, fallback_parts: int) -> list[int]:
    if not isinstance(raw, list):
        return [total] if fallback_parts <= 1 else _balanced_composition(total, fallback_parts)
    values = [max(1, _to_int(value, 1)) for value in raw if _to_int(value, 0) > 0]
    if not values:
        return [total] if fallback_parts <= 1 else _balanced_composition(total, fallback_parts)
    scale = sum(values)
    out: list[int] = []
    assigned = 0
    for value in values[:-1]:
        piece = max(1, round(value / scale * total))
        out.append(piece)
        assigned += piece
    out.append(max(1, total - assigned))
    while sum(out) > total and len(out) > 1:
        idx = max(range(len(out)), key=out.__getitem__)
        out[idx] -= 1
        if out[idx] <= 0:
            del out[idx]
    while sum(out) < total:
        out[-1] += 1
    return out


def _balanced_composition(total: int, parts: int) -> list[int]:
    parts = max(1, min(parts, total))
    base, rem = divmod(total, parts)
    return [base + (1 if idx < rem else 0) for idx in range(parts)]


def _quadratic_program_payload(
    raw_payload: Any,
    *,
    n: int,
    grid: int,
) -> dict[str, Any]:
    payload_in = raw_payload if isinstance(raw_payload, dict) else {}
    active_n = max(1, n)
    t = max(1, min(8, _to_int(payload_in.get("t", math.ceil(math.log2(max(2, active_n)))), 1)))
    coeff_bound = max(1, min(16, _to_int(payload_in.get("coeff_bound", 4), 4)))
    feature_count = _program_feature_count(t)
    decoder = str(payload_in.get("decoder", "thin_segments"))
    if decoder not in _MISR_PROGRAM_DECODERS:
        decoder = "thin_segments"
    coeffs_in = payload_in.get("coeffs", {})
    if not isinstance(coeffs_in, dict):
        coeffs_in = {}
    coeffs = {
        name: _clean_program_coeffs(coeffs_in.get(name), name, feature_count, coeff_bound)
        for name in ("a", "b", "c", "d")
    }
    composition = _clean_composition(
        payload_in.get("composition"),
        active_n,
        fallback_parts=max(1, min(active_n, t + 1)),
    )
    return {
        "generator": "bounded_quadratic_integer_program",
        "active_n": active_n,
        "program_n": 1 << t,
        "t": t,
        "grid": max(2, grid + 2),
        "decoder": decoder,
        "composition": composition,
        "coeff_bound": coeff_bound,
        "coeffs": coeffs,
        "require_triangle_free": bool(payload_in.get("require_triangle_free", True)),
    }


def _rectangles_from_quadratic_program_payload(payload: dict[str, Any], *, grid: int) -> list[list[int]]:
    t = max(1, _to_int(payload.get("t", 1), 1))
    active_n = max(1, _to_int(payload.get("active_n", 1), 1))
    side = max(2, _to_int(payload.get("grid", grid + 2), grid + 2))
    decoder = str(payload.get("decoder", "thin_segments"))
    coeffs_raw = payload.get("coeffs", {})
    if not isinstance(coeffs_raw, dict):
        coeffs_raw = {}
    feature_count = _program_feature_count(t)
    bound = max(1, _to_int(payload.get("coeff_bound", 4), 4))
    coeffs = {
        name: _clean_program_coeffs(coeffs_raw.get(name), name, feature_count, bound)
        for name in ("a", "b", "c", "d")
    }
    rects: list[list[int]] = []
    for idx in range(active_n):
        a = _program_value(coeffs["a"], idx, t, side)
        b = _program_value(coeffs["b"], idx, t, side)
        c = _program_value(coeffs["c"], idx, t, side)
        d = _program_value(coeffs["d"], idx, t, side)
        if decoder == "endpoints":
            x1, x2 = sorted((a, b))
            y1, y2 = sorted((c, d))
            rect = [x1, min(side, max(x1 + 1, x2 + 1)), y1, min(side, max(y1 + 1, y2 + 1))]
        elif decoder == "center_size":
            width = 1 + b % max(1, min(4, side))
            height = 1 + d % max(1, min(4, side))
            x1 = max(0, min(side - width, a - width // 2))
            y1 = max(0, min(side - height, c - height // 2))
            rect = [x1, x1 + width, y1, y1 + height]
        else:
            if idx % 2:
                width = 1 + (b % 2)
                height = 1 + (d % max(1, min(5, side)))
            else:
                width = 1 + (b % max(1, min(5, side)))
                height = 1 + (d % 2)
            x1 = max(0, min(side - width, a))
            y1 = max(0, min(side - height, c))
            rect = [x1, x1 + width, y1, y1 + height]
        rects.append(rect)
    return rects


def _misr_instance(representation: str, rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    if representation == "endpoint_sequence_pair":
        return _misr_endpoint_sequence_pair(rng, n=n)
    if representation == "rect_direct":
        return _tag(GENERATORS["misr"](rng, n=n, grid=grid), representation, {"generator": "direct_coordinates"})
    if representation == "graph_realized":
        return _misr_graph_realized(rng, n=n, grid=grid)
    if representation == "clique_layer_grammar":
        return _misr_clique_layers(rng, n=n, grid=grid)
    if representation == "triangle_free_rect":
        return _misr_triangle_free_rectangles(rng, n=n, grid=grid)
    if representation == "quadratic_program_rectangles":
        return _misr_quadratic_program_rectangles(rng, n=n, grid=grid)
    if representation == "fixed_symmetry_rectangles":
        rectangles = _canonicalize_d4_rectangles(GENERATORS["misr"](rng, n=n, grid=grid)["rectangles"])
        return _tag(
            {"schema": "misr_instance_v1", "rectangles": rectangles},
            representation,
            {
                "generator": "random_fixed_cardinality_rectangles",
                "target_n": len(rectangles),
                "symmetry_group": "D4_translation",
            },
        )
    raise ValueError(f"unknown MISR representation: {representation}")


def _misr_endpoint_sequence_pair(rng: random.Random, *, n: int) -> dict[str, Any]:
    size = max(1, n)
    h_seq, v_seq, generator = misr_sequences.seeded_pair(size, rng)
    rectangles = misr_sequences.rectangles_from_pair(h_seq, v_seq)
    return _tag(
        {"schema": "misr_instance_v1", "rectangles": rectangles},
        "endpoint_sequence_pair",
        misr_sequences.payload_for_pair(h_seq, v_seq, generator=generator),
    )


def _misr_graph_realized(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    clusters = max(2, min(5, int(n**0.5) + 1))
    centers = [(rng.randrange(0, grid + 1), rng.randrange(0, grid + 1)) for _ in range(clusters)]
    rectangles = []
    skeleton = []
    for idx in range(n):
        cluster = rng.randrange(clusters)
        cx, cy = centers[cluster]
        wx = rng.randrange(1, max(2, grid // 2 + 1))
        wy = rng.randrange(1, max(2, grid // 2 + 1))
        jitter = 1 if rng.random() < 0.7 else 2
        x1 = max(0, cx + rng.randrange(-jitter, jitter + 1) - wx // 2)
        y1 = max(0, cy + rng.randrange(-jitter, jitter + 1) - wy // 2)
        x2 = min(grid + 2, x1 + wx)
        y2 = min(grid + 2, y1 + wy)
        if x2 <= x1:
            x2 = x1 + 1
        if y2 <= y1:
            y2 = y1 + 1
        rectangles.append([x1, x2, y1, y2])
        skeleton.append({"vertex": idx, "cluster": cluster})
    return _tag(
        {"schema": "misr_instance_v1", "rectangles": rectangles},
        "graph_realized",
        {"generator": "clustered_interval_graph_realization", "clusters": clusters, "skeleton": skeleton},
    )


def _misr_clique_layers(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    layers = max(2, min(5, int(n**0.5) + 1))
    rectangles = []
    for idx in range(n):
        layer = idx % layers
        band_y1 = max(0, (layer * max(1, grid)) // layers)
        band_y2 = min(grid + 2, band_y1 + max(1, grid // max(2, layers - 1)) + 1)
        if rng.random() < 0.55:
            x1 = rng.randrange(0, max(1, grid // 2 + 1))
            x2 = rng.randrange(max(x1 + 1, grid // 2), grid + 2)
            y1 = max(0, band_y1 + rng.choice([-1, 0, 1]))
            y2 = max(y1 + 1, band_y2 + rng.choice([0, 1]))
        else:
            x = rng.randrange(0, grid + 1)
            x1 = max(0, x - rng.randrange(0, 2))
            x2 = min(grid + 2, x + rng.randrange(1, 3))
            y1 = 0
            y2 = grid + 1
        rectangles.append([x1, max(x1 + 1, x2), y1, max(y1 + 1, y2)])
    return _tag(
        {"schema": "misr_instance_v1", "rectangles": rectangles},
        "clique_layer_grammar",
        {"generator": "layered_clique_template", "layers": layers},
    )


def _misr_triangle_free_rectangles(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    rectangles = _fill_triangle_free_dense([], rng, target_size=max(1, n), grid=grid)
    instance = {"schema": "misr_instance_v1", "rectangles": rectangles, "constraints": {"triangle_free": True}}
    return _tag(instance, "triangle_free_rect", _triangle_free_payload(rectangles))


def _misr_quadratic_program_rectangles(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    active_n = max(1, n)
    t = max(1, min(8, math.ceil(math.log2(max(2, active_n)))))
    coeff_bound = 4
    payload = {
        "generator": "bounded_quadratic_integer_program",
        "active_n": active_n,
        "program_n": 1 << t,
        "t": t,
        "grid": max(2, grid + 2),
        "decoder": rng.choice(_MISR_PROGRAM_DECODERS),
        "composition": _random_composition(rng, active_n, max(1, min(active_n, t + 1))),
        "coeff_bound": coeff_bound,
        "coeffs": _random_program_coeffs(rng, _program_feature_count(t), coeff_bound),
        "require_triangle_free": True,
    }
    rects = _rectangles_from_quadratic_program_payload(payload, grid=grid)
    rects = _triangle_free_subset(rects, grid=grid, n_min=active_n, n_max=active_n, rng=rng)
    clean = {"schema": "misr_instance_v1", "rectangles": rects, "constraints": {"triangle_free": True}}
    return _tag(clean, "quadratic_program_rectangles", payload)


def _repair_misr(
    representation: str,
    instance: dict[str, Any],
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    if representation == "fixed_symmetry_rectangles":
        target_n = _fixed_representation_target(instance, n_min=n_min, n_max=n_max)
        rects = _clean_rectangles(instance.get("rectangles"), grid=grid, n_min=target_n, n_max=target_n)
        rects = _canonicalize_d4_rectangles(rects)
        return _tag(
            {"schema": "misr_instance_v1", "rectangles": rects},
            representation,
            {
                "generator": "random_fixed_cardinality_rectangles",
                "target_n": target_n,
                "symmetry_group": "D4_translation",
            },
        )
    if representation == "endpoint_sequence_pair":
        payload_in = instance.get("_representation_payload", {})
        h_raw = payload_in.get("H") if isinstance(payload_in, dict) else None
        v_raw = payload_in.get("V") if isinstance(payload_in, dict) else None
        fallback_n = max(n_min, min(n_max, len(instance.get("rectangles", [])) or n_min))
        if h_raw is None or v_raw is None:
            rects_for_pair = _clean_rectangles(
                instance.get("rectangles"),
                grid=grid,
                n_min=n_min,
                n_max=n_max,
            )
            h_raw, v_raw = misr_sequences.pair_from_rectangles(rects_for_pair)
            fallback_n = len(rects_for_pair)
        n = max(n_min, min(n_max, misr_sequences.infer_n(h_raw, v_raw, fallback=fallback_n)))
        h_seq, v_seq = misr_sequences.clean_pair(h_raw, v_raw, n=n)
        rects = misr_sequences.rectangles_from_pair(h_seq, v_seq)
        return _tag(
            {"schema": "misr_instance_v1", "rectangles": rects},
            representation,
            misr_sequences.payload_for_pair(h_seq, v_seq, generator="repaired_endpoint_sequences"),
        )
    if representation == "quadratic_program_rectangles":
        target_n = max(n_min, min(n_max, len(instance.get("rectangles", [])) or n_min))
        payload = _quadratic_program_payload(
            instance.get("_representation_payload", {}),
            n=target_n,
            grid=grid,
        )
        rects = _rectangles_from_quadratic_program_payload(payload, grid=grid)
        rects = _clean_rectangles(rects, grid=grid, n_min=n_min, n_max=n_max)
        if payload.get("require_triangle_free", True):
            rects = _triangle_free_subset(rects, grid=grid, n_min=n_min, n_max=n_max)
            clean = {
                "schema": "misr_instance_v1",
                "rectangles": rects,
                "constraints": {"triangle_free": True},
            }
        else:
            clean = {"schema": "misr_instance_v1", "rectangles": rects}
        payload["active_n"] = len(rects)
        payload["triangle_free"] = _is_triangle_free_rectangles(rects)
        payload["edge_count"] = sum(_popcount(mask) for mask in _intersection_masks(rects)) // 2
        return _tag(clean, representation, payload)
    rects = _clean_rectangles(instance.get("rectangles"), grid=grid, n_min=n_min, n_max=n_max)
    clean = {"schema": "misr_instance_v1", "rectangles": rects}
    if representation == "triangle_free_rect":
        rects = _triangle_free_subset(rects, grid=grid, n_min=n_min, n_max=n_max)
        clean = {
            "schema": "misr_instance_v1",
            "rectangles": rects,
            "constraints": {"triangle_free": True},
        }
        payload = _triangle_free_payload(rects)
    elif representation == "rect_direct":
        payload = {"generator": "direct_coordinates", "n": len(rects)}
    elif representation == "graph_realized":
        fallback_clusters = max(2, min(5, int(max(1, len(rects)) ** 0.5) + 1))
        payload_in = instance.get("_representation_payload", {})
        clusters = fallback_clusters
        if isinstance(payload_in, dict):
            clusters = max(1, _to_int(payload_in.get("clusters", fallback_clusters), fallback_clusters))
        skeleton = []
        sums = [[0.0, 0.0, 0] for _ in range(clusters)]
        for idx, rect in enumerate(rects):
            cx = (rect[0] + rect[1]) / 2.0
            cy = (rect[2] + rect[3]) / 2.0
            cluster = min(clusters - 1, max(0, int(cx / max(1, grid + 2) * clusters)))
            skeleton.append({"vertex": idx, "cluster": cluster})
            sums[cluster][0] += cx
            sums[cluster][1] += cy
            sums[cluster][2] += 1
        centers = [
            [round(row[0] / row[2], 4), round(row[1] / row[2], 4)] if row[2] else [0.0, 0.0]
            for row in sums
        ]
        edge_count = sum(
            1
            for i, rect in enumerate(rects)
            for other in rects[i + 1 :]
            if _rect_intersects(rect, other)
        )
        payload = {
            "generator": "clustered_interval_graph_realization",
            "clusters": clusters,
            "cluster_centers": centers,
            "skeleton": skeleton,
            "edge_count": edge_count,
        }
    elif representation == "clique_layer_grammar":
        layers = _payload_layers(instance, max(2, min(5, int(max(1, len(rects)) ** 0.5) + 1)))
        assignments = []
        for idx, rect in enumerate(rects):
            y_mid = (rect[2] + rect[3]) / 2.0
            layer = min(layers - 1, max(0, int(y_mid / max(1, grid + 2) * layers)))
            assignments.append({"rectangle": idx, "layer": layer})
        payload = {
            "generator": "layered_clique_template",
            "layers": layers,
            "assignments": assignments,
        }
    else:
        raise ValueError(f"unknown MISR representation: {representation}")
    return _tag(clean, representation, payload)


def _unit_square_instance(representation: str, rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    if representation == "square_direct":
        return _tag(GENERATORS["unit_square"](rng, n=n, grid=grid), representation, {"generator": "direct_coordinates"})
    if representation == "line_square_incidence":
        return _unit_square_incidence(rng, n=n, grid=grid)
    if representation == "threshold_layer_grammar":
        return _unit_square_threshold_layers(rng, n=n, grid=grid)
    if representation == "sqstab_exact_grid":
        return _unit_square_sqstab_exact_grid(rng, n=n, grid=grid)
    if representation == "fixed_symmetry_grid":
        side = _fixed_symmetry_grid_side(grid)
        squares = _canonicalize_d4_squares(_random_unique_squares(rng, n=max(1, n), grid=grid))
        return _tag(
            {"schema": "unit_square_instance_v1", "squares": squares, "side": side},
            representation,
            {
                "generator": "random_fixed_cardinality_grid",
                "target_n": len(squares),
                "side": side,
                "side_rule": "fixed_Q2",
                "symmetry_group": "D4_translation",
            },
        )
    raise ValueError(f"unknown unit-square representation: {representation}")


def _unit_square_side(instance: dict[str, Any], *, grid: int) -> int:
    raw = instance.get("side", 1)
    return max(1, min(max(1, grid + 2), _to_int(raw, 1)))


def _fixed_symmetry_grid_side(grid: int) -> int:
    return 2 if grid >= 2 else 1


def _normalize_square_coordinates(squares: list[list[int]]) -> list[list[int]]:
    if not squares:
        return []
    min_x = min(x for x, _ in squares)
    min_y = min(y for _, y in squares)
    normalized = sorted({(x - min_x, y - min_y) for x, y in squares})
    return [[x, y] for x, y in normalized]


def _unit_square_sqstab_exact_grid(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    side = rng.randrange(1, max(2, min(grid + 2, 4)) + 1)
    squares = _random_unique_squares(rng, n=max(1, n), grid=grid)
    clean = {"schema": "unit_square_instance_v1", "squares": squares, "side": side}
    payload = {
        "generator": "sqstab_exact_grid_random",
        "side": side,
        "requested_n": n,
        "canonical": _normalize_square_coordinates(squares),
    }
    return _tag(clean, "sqstab_exact_grid", payload)


def _random_unique_squares(rng: random.Random, *, n: int, grid: int) -> list[list[int]]:
    target = max(1, n)
    side = max(1, grid + 1)
    seen: set[tuple[int, int]] = set()
    squares: list[list[int]] = []
    attempts = 0
    while len(squares) < target and attempts < max(100, target * 20):
        attempts += 1
        candidate = (rng.randrange(side), rng.randrange(side))
        if candidate in seen:
            continue
        seen.add(candidate)
        squares.append([candidate[0], candidate[1]])
    cursor = 0
    while len(squares) < target:
        candidate = (cursor % side, cursor // side)
        cursor += 1
        if candidate in seen:
            continue
        seen.add(candidate)
        squares.append([candidate[0], candidate[1]])
    return squares


def _unit_square_incidence(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    cols = max(2, min(grid + 1, int(n**0.5) + 2))
    rows = max(2, min(grid + 1, (n + cols - 1) // cols + 1))
    squares = []
    incidence = []
    for idx in range(n):
        col = (idx + rng.randrange(cols)) % cols
        row = (idx * 2 + rng.randrange(rows)) % rows
        x = min(grid, max(0, col * max(1, grid) // max(1, cols - 1)))
        y = min(grid, max(0, row * max(1, grid) // max(1, rows - 1)))
        if rng.random() < 0.35:
            x = max(0, min(grid, x + rng.choice([-1, 1])))
        if rng.random() < 0.35:
            y = max(0, min(grid, y + rng.choice([-1, 1])))
        squares.append([x, y])
        incidence.append({"square": idx, "column": col, "row": row})
    return _tag(
        {"schema": "unit_square_instance_v1", "squares": squares},
        "line_square_incidence",
        {"generator": "balanced_line_square_incidence", "columns": cols, "rows": rows, "incidence": incidence},
    )


def _unit_square_threshold_layers(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    layers = max(2, min(6, int(n**0.5) + 2))
    squares = []
    for idx in range(n):
        layer = idx % layers
        threshold = (idx * 2 + layer + rng.randrange(layers)) % max(1, grid + 1)
        x = (threshold + layer) % max(1, grid + 1)
        y = (threshold * 2 - layer) % max(1, grid + 1)
        if rng.random() < 0.4:
            x = max(0, min(grid, x + rng.choice([-1, 0, 1])))
        if rng.random() < 0.4:
            y = max(0, min(grid, y + rng.choice([-1, 0, 1])))
        squares.append([x, y])
    return _tag(
        {"schema": "unit_square_instance_v1", "squares": squares},
        "threshold_layer_grammar",
        {"generator": "cyclic_threshold_layers", "layers": layers},
    )


def _repair_unit_square(
    representation: str,
    instance: dict[str, Any],
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    side = _unit_square_side(instance, grid=grid)
    if representation == "fixed_symmetry_grid":
        side = _fixed_symmetry_grid_side(grid)
        target_n = _fixed_representation_target(instance, n_min=n_min, n_max=n_max)
        capacity = (grid + 1) ** 2
        if target_n > capacity:
            raise ValueError(f"fixed_symmetry_grid needs {target_n} distinct cells but grid capacity is {capacity}")
        squares = _canonicalize_d4_squares(
            _clean_squares(instance.get("squares"), grid=grid, n_min=0, n_max=target_n)
        )
        seen = {tuple(square) for square in squares}
        cursor = 0
        while len(squares) < target_n:
            candidate = (cursor % (grid + 1), cursor // (grid + 1))
            cursor += 1
            if candidate in seen:
                continue
            seen.add(candidate)
            squares.append([candidate[0], candidate[1]])
        squares = _canonicalize_d4_squares(squares)
        clean = {"schema": "unit_square_instance_v1", "squares": squares, "side": side}
        return _tag(
            clean,
            representation,
            {
                "generator": "random_fixed_cardinality_grid",
                "target_n": target_n,
                "side": side,
                "side_rule": "fixed_Q2",
                "symmetry_group": "D4_translation",
            },
        )
    squares = _clean_squares(instance.get("squares"), grid=grid, n_min=n_min, n_max=n_max)
    clean = {"schema": "unit_square_instance_v1", "squares": squares}
    if side != 1 or representation == "sqstab_exact_grid":
        clean["side"] = side
    if representation == "square_direct":
        payload = {"generator": "direct_coordinates", "n": len(squares)}
    elif representation == "line_square_incidence":
        fallback_cols = max(2, min(grid + 1, int(max(1, len(squares)) ** 0.5) + 2))
        fallback_rows = max(2, min(grid + 1, (len(squares) + fallback_cols - 1) // fallback_cols + 1))
        payload_in = instance.get("_representation_payload", {})
        if isinstance(payload_in, dict):
            cols = max(1, _to_int(payload_in.get("columns", fallback_cols), fallback_cols))
            rows = max(1, _to_int(payload_in.get("rows", fallback_rows), fallback_rows))
        else:
            cols, rows = fallback_cols, fallback_rows
        incidence = []
        for idx, (x, y) in enumerate(squares):
            col = min(cols - 1, round(x / max(1, grid) * max(0, cols - 1)))
            row = min(rows - 1, round(y / max(1, grid) * max(0, rows - 1)))
            incidence.append({"square": idx, "column": int(col), "row": int(row)})
        payload = {
            "generator": "balanced_line_square_incidence",
            "columns": cols,
            "rows": rows,
            "incidence": incidence,
        }
    elif representation == "threshold_layer_grammar":
        layers = _payload_layers(instance, max(2, min(6, int(max(1, len(squares)) ** 0.5) + 2)))
        assignments = []
        for idx, (x, y) in enumerate(squares):
            layer = (x - y) % layers
            threshold = (x + y + layer) % max(1, grid + 1)
            assignments.append({"square": idx, "layer": layer, "threshold": threshold})
        payload = {
            "generator": "cyclic_threshold_layers",
            "layers": layers,
            "assignments": assignments,
        }
    elif representation == "sqstab_exact_grid":
        side = max(1, side)
        squares = _normalize_square_coordinates(squares)
        cursor = 0
        seen = {tuple(row) for row in squares}
        while len(squares) < n_min:
            candidate = [cursor % max(1, grid + 1), cursor // max(1, grid + 1)]
            cursor += 1
            if tuple(candidate) in seen:
                continue
            seen.add(tuple(candidate))
            squares.append(candidate)
        squares = squares[:n_max]
        clean = {"schema": "unit_square_instance_v1", "squares": squares, "side": side}
        payload_in = instance.get("_representation_payload", {})
        generator = "sqstab_exact_grid_random"
        if isinstance(payload_in, dict):
            generator = str(payload_in.get("generator") or generator)
        payload = {
            "generator": generator,
            "side": side,
            "canonical": _normalize_square_coordinates(squares),
            "n": len(squares),
        }
    else:
        raise ValueError(f"unknown unit-square representation: {representation}")
    return _tag(clean, representation, payload)


def _guillotine_instance(representation: str, rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    if representation == "rect_direct_disjoint":
        return _tag(GENERATORS["guillotine"](rng, n=n, grid=grid), representation, {"generator": "direct_disjoint_cells"})
    if representation == "sequence_pair_packing":
        return _guillotine_sequence_pair(rng, n=n, grid=grid)
    if representation == "recursive_obstruction_grammar":
        return _guillotine_recursive_obstruction(rng, n=n, grid=grid)
    if representation == "fixed_symmetry_packing":
        rectangles = _canonicalize_d4_rectangles(_guillotine_random_valid_rects(rng, n=n, grid=grid))
        return _tag(
            {"schema": "guillotine_instance_v1", "rectangles": rectangles},
            representation,
            {
                "generator": "random_fixed_cardinality_packing",
                "target_n": len(rectangles),
                "symmetry_group": "D4_translation",
            },
        )
    raise ValueError(f"unknown guillotine representation: {representation}")


def _guillotine_sequence_pair(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    order = list(range(n))
    rng.shuffle(order)
    rectangles = []
    x = y = shelf_height = 0
    max_width = max(2, grid + 1)
    for _idx in order:
        width = rng.randrange(1, max(2, min(3, grid) + 1))
        height = rng.randrange(1, max(2, min(3, grid) + 1))
        if x + width > max_width:
            x = 0
            y += max(1, shelf_height)
            shelf_height = 0
        rectangles.append([x, x + width, y, y + height])
        x += width
        shelf_height = max(shelf_height, height)
    return _tag(
        {"schema": "guillotine_instance_v1", "rectangles": rectangles},
        "sequence_pair_packing",
        {"generator": "shelf_sequence_pair", "order": order},
    )


def _guillotine_recursive_obstruction(rng: random.Random, *, n: int, grid: int) -> dict[str, Any]:
    rectangles = _guillotine_obstruction_rectangles(rng, grid=grid, n=n)
    return _tag(
        {"schema": "guillotine_instance_v1", "rectangles": rectangles},
        "recursive_obstruction_grammar",
        {
            "generator": "random_recursive_obstruction",
            "requested_n": n,
            "actual_n": len(rectangles),
        },
    )


def _guillotine_obstruction_rectangles(rng: random.Random, *, grid: int, n: int) -> list[list[int]]:
    target = max(1, n)
    if target < 7:
        return _guillotine_random_valid_rects(rng, n=target, grid=grid)

    rects: list[list[int]] = []
    filler_width = max(grid + 2, target + 2)
    max_cores = max(1, min(4, target // 10))
    min_cores = max(1, max_cores - 1)
    core_count = rng.randrange(min_cores, max_cores + 1)
    x_cursor = filler_width + rng.randrange(5, 10)
    for _ in range(core_count):
        core = _guillotine_spiral_obstruction_core(rng, origin_x=x_cursor, origin_y=rng.randrange(0, 4))
        rects.extend(core)
        x_cursor = max(rect[1] for rect in rects) + rng.randrange(5, 10)
        if len(rects) + 7 > target:
            break

    filler = 0
    while len(rects) < target:
        x = filler % filler_width
        y = filler // filler_width
        rects.append([x, x + 1, y, y + 1])
        filler += 1
    return _guillotine_canonicalize(rects[:target])


_GUILLOTINE_SPIRAL_TOPOLOGY: tuple[tuple[int, int, int, int], ...] = (
    (6, 8, 0, 1),
    (2, 7, 3, 4),
    (7, 8, 1, 4),
    (3, 5, 0, 3),
    (4, 6, 4, 7),
    (0, 1, 2, 5),
    (0, 4, 6, 7),
)


def _guillotine_spiral_obstruction_core(
    rng: random.Random,
    *,
    origin_x: int,
    origin_y: int,
) -> list[list[int]]:
    x_coords = [0]
    for _ in range(8):
        x_coords.append(x_coords[-1] + rng.randrange(1, 4))
    y_coords = [0]
    for _ in range(7):
        y_coords.append(y_coords[-1] + rng.randrange(1, 4))
    rects = [
        [origin_x + x_coords[x1], origin_x + x_coords[x2], origin_y + y_coords[y1], origin_y + y_coords[y2]]
        for x1, x2, y1, y2 in _GUILLOTINE_SPIRAL_TOPOLOGY
    ]
    if rng.random() < 0.5:
        xmin = min(rect[0] for rect in rects)
        xmax = max(rect[1] for rect in rects)
        rects = [[xmin + xmax - rect[1], xmin + xmax - rect[0], rect[2], rect[3]] for rect in rects]
    if rng.random() < 0.5:
        ymin = min(rect[2] for rect in rects)
        ymax = max(rect[3] for rect in rects)
        rects = [[rect[0], rect[1], ymin + ymax - rect[3], ymin + ymax - rect[2]] for rect in rects]
    if rng.random() < 0.5:
        rects = [
            [origin_x + rect[2] - origin_y, origin_x + rect[3] - origin_y, origin_y + rect[0] - origin_x, origin_y + rect[1] - origin_x]
            for rect in rects
        ]
    return rects


def _guillotine_dynamic_side(*, grid: int, n: int, rects: list[list[int]] | None = None) -> int:
    observed = 0
    if rects:
        observed = max((max(rect[1], rect[3]) for rect in rects), default=0)
    return max(4, grid + 2, 2 * max(1, n), observed + 2)


def _guillotine_random_rect(rng: random.Random, *, side: int) -> list[int]:
    typ = rng.randrange(100)
    if typ < 40:
        width = rng.randrange(2, max(3, side // 2 + 1))
        height = rng.randrange(1, max(2, side // 8 + 1))
    elif typ < 80:
        width = rng.randrange(1, max(2, side // 8 + 1))
        height = rng.randrange(2, max(3, side // 2 + 1))
    else:
        width = rng.randrange(1, max(2, side // 4 + 1))
        height = rng.randrange(1, max(2, side // 4 + 1))
    width = min(width, side)
    height = min(height, side)
    x = rng.randrange(0, max(1, side - width + 1))
    y = rng.randrange(0, max(1, side - height + 1))
    return [x, x + width, y, y + height]


def _guillotine_random_valid_rects(rng: random.Random, *, n: int, grid: int) -> list[list[int]]:
    side = _guillotine_dynamic_side(grid=grid, n=n)
    rects: list[list[int]] = []
    attempts = 0
    while len(rects) < n and attempts < max(500, n * 120):
        attempts += 1
        rect = _guillotine_random_rect(rng, side=side)
        if all(not _interior_overlap(rect, other) for other in rects):
            rects.append(rect)
    cursor = 0
    while len(rects) < n:
        x = (2 * cursor) % side
        y = (5 * cursor + 1) % side
        rect = [x, min(side, x + 1), y, min(side, y + 1)]
        cursor += 1
        if rect[0] < rect[1] and rect[2] < rect[3] and all(not _interior_overlap(rect, other) for other in rects):
            rects.append(rect)
    return _guillotine_canonicalize(rects[:n])


def _guillotine_canonicalize(rects: list[list[int]]) -> list[list[int]]:
    if not rects:
        return []
    xs = sorted({coord for rect in rects for coord in (rect[0], rect[1])})
    ys = sorted({coord for rect in rects for coord in (rect[2], rect[3])})
    xr = {value: idx for idx, value in enumerate(xs)}
    yr = {value: idx for idx, value in enumerate(ys)}
    return sorted(
        ([xr[rect[0]], xr[rect[1]], yr[rect[2]], yr[rect[3]]] for rect in rects),
        key=lambda rect: (rect[0], rect[2], rect[1], rect[3]),
    )


def _repair_guillotine(
    representation: str,
    instance: dict[str, Any],
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> dict[str, Any]:
    if representation == "fixed_symmetry_packing":
        target_n = _fixed_representation_target(instance, n_min=n_min, n_max=n_max)
        rects = _clean_guillotine_rectangles(
            instance.get("rectangles"),
            grid=grid,
            n_min=target_n,
            n_max=target_n,
        )
        rects = _disjoint_rectangles_preserving_order(rects, grid=grid, n_min=target_n)[:target_n]
        rects = _canonicalize_d4_rectangles(rects)
        return _tag(
            {"schema": "guillotine_instance_v1", "rectangles": rects},
            representation,
            {
                "generator": "random_fixed_cardinality_packing",
                "target_n": target_n,
                "symmetry_group": "D4_translation",
            },
        )
    rects = _clean_guillotine_rectangles(instance.get("rectangles"), grid=grid, n_min=n_min, n_max=n_max)
    if representation in {"rect_direct_disjoint", "sequence_pair_packing", "recursive_obstruction_grammar"}:
        rects = _disjoint_rectangles_preserving_order(rects, grid=grid, n_min=n_min)
    else:
        raise ValueError(f"unknown guillotine representation: {representation}")
    clean = {"schema": "guillotine_instance_v1", "rectangles": rects}
    if representation == "rect_direct_disjoint":
        payload = {"generator": "direct_disjoint_cells", "n": len(rects)}
    elif representation == "sequence_pair_packing":
        order = sorted(range(len(rects)), key=lambda idx: (rects[idx][0], rects[idx][2], idx))
        reverse = sorted(range(len(rects)), key=lambda idx: (rects[idx][0], -rects[idx][2], idx))
        payload = {
            "generator": "shelf_sequence_pair",
            "positive_order": order,
            "negative_order": reverse,
        }
    else:
        payload = {
            "generator": "random_recursive_obstruction",
            "actual_n": len(rects),
        }
    return _tag(clean, representation, payload)


def _clean_guillotine_rectangles(raw: Any, *, grid: int, n_min: int, n_max: int) -> list[list[int]]:
    if not isinstance(raw, list):
        raw = []
    observed = 0
    for row in raw:
        if isinstance(row, (list, tuple)) and len(row) >= 4:
            observed = max(observed, *(_to_int(value, 0) for value in row[:4]))
    side = max(grid + 2, 2 * max(1, n_min), observed + 2)
    rects: list[list[int]] = []
    for row in raw[: max(0, n_max)]:
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            continue
        x1 = max(0, min(side - 1, _to_int(row[0])))
        x2 = max(1, min(side, _to_int(row[1], x1 + 1)))
        y1 = max(0, min(side - 1, _to_int(row[2])))
        y2 = max(1, min(side, _to_int(row[3], y1 + 1)))
        if x2 <= x1:
            x2 = min(side, x1 + 1)
            x1 = max(0, x2 - 1)
        if y2 <= y1:
            y2 = min(side, y1 + 1)
            y1 = max(0, y2 - 1)
        rects.append([x1, x2, y1, y2])
    return rects


def _disjoint_rectangles_preserving_order(
    rects: list[list[int]],
    *,
    grid: int,
    n_min: int,
) -> list[list[int]]:
    clean: list[list[int]] = []
    for rect in rects:
        if all(not _interior_overlap(rect, other) for other in clean):
            clean.append(rect)
    side = _guillotine_dynamic_side(grid=grid, n=max(n_min, len(clean)), rects=clean)
    cursor = 0
    while len(clean) < n_min and cursor < side * side:
        x, y = cursor % side, cursor // side
        cursor += 1
        rect = [x, x + 1, y, y + 1]
        if all(not _interior_overlap(rect, other) for other in clean):
            clean.append(rect)
    if len(clean) < n_min:
        return _pack_rectangles_shelf(rects, grid=grid)[:n_min]
    return _guillotine_canonicalize(clean)


def _pack_rectangles_shelf(rects: list[list[int]], *, grid: int) -> list[list[int]]:
    max_width = max(2, grid + 1)
    x = 0
    y = 0
    shelf_height = 0
    packed: list[list[int]] = []
    for rect in rects:
        width = max(1, rect[1] - rect[0])
        height = max(1, rect[3] - rect[2])
        if x + width > max_width and x > 0:
            x = 0
            y += max(1, shelf_height)
            shelf_height = 0
        packed.append([x, x + width, y, y + height])
        x += width
        shelf_height = max(shelf_height, height)
    return packed


def _unit_cell_unique(
    rects: list[list[int]],
    *,
    grid: int,
    n_min: int,
    n_max: int,
) -> list[list[int]]:
    seen: set[tuple[int, int]] = set()
    cells: list[list[int]] = []
    for rect in rects:
        x = max(0, min(max(0, grid - 1), rect[0]))
        y = max(0, min(max(0, grid - 1), rect[2]))
        if (x, y) not in seen:
            seen.add((x, y))
            cells.append([x, x + 1, y, y + 1])
        if len(cells) >= n_max:
            break
    cursor = 0
    side = max(1, grid)
    while len(cells) < n_min:
        x, y = cursor % side, cursor // side
        cursor += 1
        if (x, y) in seen:
            continue
        seen.add((x, y))
        cells.append([x, x + 1, y, y + 1])
    return cells
