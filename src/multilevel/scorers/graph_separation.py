from __future__ import annotations

import itertools
import time
from typing import Any

from multilevel.canonical import attach_certificate_hash, canonical_dumps
from multilevel.numbers import json_box, parse_box
from multilevel.scorers import misr

Obj = tuple[str, int, int, int, int]


def _rectangle_graph(rectangles: list[tuple]) -> list[list[int]]:
    adj_masks = misr._intersection_graph(rectangles)
    edges = []
    n = len(rectangles)
    for i in range(n):
        for j in range(i + 1, n):
            if adj_masks[i] & (1 << j):
                edges.append([i, j])
    return edges


def _edge_set(edges: list[list[int]]) -> set[tuple[int, int]]:
    return {tuple(sorted(edge)) for edge in edges}


def _adjacency_matrix(n: int, edges: set[tuple[int, int]]) -> list[list[int]]:
    matrix = [[0] * n for _ in range(n)]
    for u, v in edges:
        matrix[u][v] = 1
        matrix[v][u] = 1
    return matrix


def _graph6(n: int, edges: set[tuple[int, int]]) -> str | None:
    """Return graph6 for small graphs using the standard upper-triangle order."""
    if n > 62:
        return None
    bits = []
    for i in range(n):
        for j in range(i + 1, n):
            bits.append(1 if (i, j) in edges else 0)
    while len(bits) % 6:
        bits.append(0)
    chars = [chr(n + 63)]
    for offset in range(0, len(bits), 6):
        value = 0
        for bit in bits[offset : offset + 6]:
            value = (value << 1) | bit
        chars.append(chr(value + 63))
    return "".join(chars)


def _automorphism_group_size(n: int, adjacency: list[list[int]]) -> int | None:
    """Brute-force automorphism count for the small graphs used in exploration."""
    if n > 9:
        return None
    degrees = [sum(row) for row in adjacency]
    classes: dict[int, list[int]] = {}
    for vertex, degree in enumerate(degrees):
        classes.setdefault(degree, []).append(vertex)
    class_vertices = list(classes.values())
    count = 0
    for blocks in itertools.product(*(itertools.permutations(block) for block in class_vertices)):
        perm = list(range(n))
        for original_block, image_block in zip(class_vertices, blocks):
            for vertex, image in zip(original_block, image_block):
                perm[vertex] = image
        ok = True
        for i in range(n):
            pi = perm[i]
            for j in range(i + 1, n):
                if adjacency[i][j] != adjacency[pi][perm[j]]:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            count += 1
    return count


def _max_subset_size(n: int, edges: set[tuple[int, int]], *, want_clique: bool) -> int:
    best = 0
    for mask in range(1, 1 << n):
        size = bin(mask).count("1")
        if size <= best:
            continue
        ok = True
        vertices = [idx for idx in range(n) if mask & (1 << idx)]
        for i, u in enumerate(vertices):
            for v in vertices[i + 1 :]:
                adjacent = tuple(sorted((u, v))) in edges
                if adjacent != want_clique:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            best = size
    return best


def _mixed_objects(grid: int) -> list[Obj]:
    objs: list[Obj] = []
    for size in range(1, grid + 1):
        for x in range(0, grid - size + 1):
            for y in range(0, grid - size + 1):
                objs.append(("square", x, x + size, y, y + size))
    for y in range(0, grid + 1):
        for x1 in range(0, grid):
            for x2 in range(x1 + 1, grid + 1):
                objs.append(("hseg", x1, x2, y, y))
    for x in range(0, grid + 1):
        for y1 in range(0, grid):
            for y2 in range(y1 + 1, grid + 1):
                objs.append(("vseg", x, x, y1, y2))
    return objs


def _intersects(a: Obj, b: Obj) -> bool:
    _, ax1, ax2, ay1, ay2 = a
    _, bx1, bx2, by1, by2 = b
    return max(ax1, bx1) <= min(ax2, bx2) and max(ay1, by1) <= min(ay2, by2)


def _find_mixed_representation(
    n: int,
    edges: set[tuple[int, int]],
    objects: list[Obj],
    timeout_seconds: float,
) -> list[Obj] | None:
    start = time.perf_counter()
    degrees = [0] * n
    for u, v in edges:
        degrees[u] += 1
        degrees[v] += 1
    order = sorted(range(n), key=lambda v: degrees[v], reverse=True)
    assignment: dict[int, Obj] = {}

    def compatible(vertex: int, obj_idx: int) -> bool:
        obj = objects[obj_idx]
        for other_vertex, other_obj in assignment.items():
            should_intersect = tuple(sorted((vertex, other_vertex))) in edges
            if _intersects(obj, other_obj) != should_intersect:
                return False
        return True

    def dfs(pos: int) -> bool:
        if time.perf_counter() - start > timeout_seconds:
            raise TimeoutError
        if pos == n:
            return True
        vertex = order[pos]
        for obj_idx, obj in enumerate(objects):
            if compatible(vertex, obj_idx):
                assignment[vertex] = obj
                if dfs(pos + 1):
                    return True
                del assignment[vertex]
        return False

    try:
        if dfs(0):
            return [assignment[i] for i in range(n)]
    except TimeoutError:
        raise
    return None


def score_instance(instance: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    rectangles = [parse_box(row) for row in instance["rectangles"]]
    for rect in rectangles:
        x1, x2, y1, y2 = rect
        if not (x1 < x2 and y1 < y2):
            raise ValueError(f"invalid rectangle: {rect!r}")
    n = len(rectangles)
    if n == 0:
        raise ValueError("graph-separation instance must contain rectangles")
    grid = int(instance.get("mixed_grid", 3))
    timeout_seconds = float(instance.get("timeout_seconds", 5.0))
    edges = _rectangle_graph(rectangles)
    edge_set = _edge_set(edges)
    adjacency = _adjacency_matrix(n, edge_set)
    degree_sequence = sorted((sum(row) for row in adjacency), reverse=True)
    edge_count = len(edges)
    density = edge_count / max(1, n * (n - 1) / 2)
    objects = _mixed_objects(grid)
    status = "unknown"
    assignment = None
    try:
        assignment = _find_mixed_representation(n, edge_set, objects, timeout_seconds)
        status = "representable" if assignment is not None else "bounded_grid_infeasible"
    except TimeoutError:
        status = "timeout"

    score = 1.0 if status == "bounded_grid_infeasible" else 0.0
    cert = {
        "schema": "graph_separation_certificate_v1",
        "problem": "graph_separation",
        "rectangles": [json_box(rect) for rect in rectangles],
        "n": n,
        "rectangle_edges": edges,
        "edge_count": edge_count,
        "edge_density": density,
        "adjacency_matrix": adjacency,
        "graph6": _graph6(n, edge_set),
        "degree_sequence": degree_sequence,
        "clique_number": _max_subset_size(n, edge_set, want_clique=True),
        "independence_number": _max_subset_size(n, edge_set, want_clique=False),
        "automorphism_group_size": _automorphism_group_size(n, adjacency),
        "mixed_grid": grid,
        "mixed_candidate_count": len(objects),
        "mixed_status": status,
        "mixed_assignment": None if assignment is None else [list(obj) for obj in assignment],
        "score": score,
        "unconditional_separation": False,
        "bounded_evidence_only": True,
        "evidence_note": (
            "bounded-grid infeasibility is not an unconditional separation"
            if status == "bounded_grid_infeasible"
            else "candidate has a bounded-grid mixed square/segment representation or timed out"
        ),
        "solver": {
            "solver": "bounded_grid_backtracking_search",
            "mixed_object_family": "axis_aligned_squares_and_segments",
            "mixed_grid": grid,
            "timeout_seconds": timeout_seconds,
            "candidate_objects": len(objects),
        },
        "solver_status": status,
        "exact_runtime_seconds": time.perf_counter() - start,
    }
    cert["certificate_payload_bytes"] = len(canonical_dumps(cert).encode("utf-8"))
    return attach_certificate_hash(cert)


def verify_certificate(cert: dict[str, Any], tolerance: float = 1e-8) -> bool:
    recomputed = score_instance(
        {
            "rectangles": cert["rectangles"],
            "mixed_grid": cert["mixed_grid"],
            "timeout_seconds": max(5.0, float(cert.get("exact_runtime_seconds", 0.0)) + 1.0),
        }
    )
    return (
        cert.get("rectangle_edges") == recomputed.get("rectangle_edges")
        and cert.get("mixed_status") == recomputed.get("mixed_status")
        and abs(float(cert.get("score")) - float(recomputed.get("score"))) <= tolerance
    )
