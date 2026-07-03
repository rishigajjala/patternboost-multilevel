from __future__ import annotations

import random
from typing import Any


def random_misr_instance(rng: random.Random, *, n: int = 12, grid: int = 12) -> dict[str, Any]:
    rectangles = []
    for _ in range(n):
        x1 = rng.randrange(0, grid)
        x2 = rng.randrange(x1 + 1, grid + 2)
        y1 = rng.randrange(0, grid)
        y2 = rng.randrange(y1 + 1, grid + 2)
        rectangles.append([x1, x2, y1, y2])
    return {"schema": "misr_instance_v1", "rectangles": rectangles}


def random_unit_square_instance(
    rng: random.Random, *, n: int = 12, grid: int = 8
) -> dict[str, Any]:
    squares = [[rng.randrange(0, grid), rng.randrange(0, grid)] for _ in range(n)]
    return {"schema": "unit_square_instance_v1", "squares": squares}


def random_guillotine_instance(
    rng: random.Random, *, n: int = 12, grid: int = 8
) -> dict[str, Any]:
    cells = [(x, y) for x in range(grid) for y in range(grid)]
    rng.shuffle(cells)
    chosen = cells[: min(n, len(cells))]
    rectangles = [[x, x + 1, y, y + 1] for x, y in chosen]
    return {"schema": "guillotine_instance_v1", "rectangles": rectangles}


def random_graph_separation_instance(
    rng: random.Random, *, n: int = 5, grid: int = 4
) -> dict[str, Any]:
    rectangles = []
    for _ in range(n):
        x1 = rng.randrange(0, grid)
        x2 = rng.randrange(x1 + 1, grid + 2)
        y1 = rng.randrange(0, grid)
        y2 = rng.randrange(y1 + 1, grid + 2)
        rectangles.append([x1, x2, y1, y2])
    return {
        "schema": "graph_separation_instance_v1",
        "rectangles": rectangles,
        "mixed_grid": min(4, max(2, grid)),
        "timeout_seconds": 3.0,
    }


def random_epsilon_net_instance(
    rng: random.Random, *, n: int = 7, grid: int = 6
) -> dict[str, Any]:
    seen = set()
    points = []
    while len(points) < n:
        point = (rng.randrange(0, grid + 1), rng.randrange(0, grid + 1))
        if point not in seen:
            seen.add(point)
            points.append([point[0], point[1]])
    threshold = max(1, n // 2)
    k = max(1, min(n - 1, threshold - 1))
    return {
        "schema": "epsilon_net_instance_v1",
        "points": points,
        "threshold": threshold,
        "k": k,
    }


GENERATORS = {
    "misr": random_misr_instance,
    "unit_square": random_unit_square_instance,
    "guillotine": random_guillotine_instance,
    "graph_separation": random_graph_separation_instance,
    "epsilon_net": random_epsilon_net_instance,
}
