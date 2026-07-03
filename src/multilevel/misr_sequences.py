from __future__ import annotations

import random
from collections import Counter
from typing import Any


Seq = list[int]


def clean_sequence(raw: Any, n: int) -> Seq:
    """Return a length-2n sequence with each label 1..n exactly twice."""
    if not isinstance(raw, (list, tuple)):
        raw = []
    counts = {label: 0 for label in range(1, n + 1)}
    seq: Seq = []
    for value in raw:
        try:
            label = int(round(float(value)))
        except Exception:
            continue
        if 1 <= label <= n and counts[label] < 2:
            seq.append(label)
            counts[label] += 1
    for label in range(1, n + 1):
        while counts[label] < 2:
            seq.append(label)
            counts[label] += 1
    return seq[: 2 * n]


def is_valid_sequence(seq: Seq, n: int | None = None) -> bool:
    if n is None:
        n = max(seq, default=0)
    return len(seq) == 2 * n and Counter(seq) == Counter({label: 2 for label in range(1, n + 1)})


def infer_n(h_seq: Any, v_seq: Any, *, fallback: int) -> int:
    labels = []
    for raw in (h_seq, v_seq):
        if isinstance(raw, (list, tuple)):
            for value in raw:
                try:
                    labels.append(int(round(float(value))))
                except Exception:
                    pass
    return max(1, max(labels, default=fallback), fallback)


def canonicalize_pair(h_seq: Seq, v_seq: Seq) -> tuple[Seq, Seq]:
    order: list[int] = []
    seen: set[int] = set()
    for label in h_seq:
        if label not in seen:
            order.append(label)
            seen.add(label)
    relabel = {old: new for new, old in enumerate(order, 1)}
    return [relabel[label] for label in h_seq], [relabel[label] for label in v_seq]


def clean_pair(h_seq: Any, v_seq: Any, *, n: int) -> tuple[Seq, Seq]:
    h = clean_sequence(h_seq, n)
    v = clean_sequence(v_seq, n)
    return canonicalize_pair(h, v)


def seq_spans(seq: Seq) -> list[tuple[int, int]]:
    first: dict[int, int] = {}
    spans: dict[int, tuple[int, int]] = {}
    for idx, label in enumerate(seq):
        if label in first:
            spans[label] = (first[label], idx)
        else:
            first[label] = idx
    return [spans[label] for label in range(1, max(seq, default=0) + 1)]


def rectangles_from_pair(h_seq: Seq, v_seq: Seq) -> list[list[int]]:
    x_spans = seq_spans(h_seq)
    y_spans = seq_spans(v_seq)
    rectangles: list[list[int]] = []
    for (x1, x2), (y1, y2) in zip(x_spans, y_spans):
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        rectangles.append([x1, x2, y1, y2])
    return rectangles


def pair_from_rectangles(rectangles: list[list[int]]) -> tuple[Seq, Seq]:
    h_events: list[tuple[int, int, int]] = []
    v_events: list[tuple[int, int, int]] = []
    for idx, rect in enumerate(rectangles, start=1):
        x1, x2, y1, y2 = rect
        h_events.append((int(x1), 0, idx))
        h_events.append((int(x2), 1, idx))
        v_events.append((int(y1), 0, idx))
        v_events.append((int(y2), 1, idx))
    h = [label for _, _, label in sorted(h_events)]
    v = [label for _, _, label in sorted(v_events)]
    return canonicalize_pair(h, v)


def random_valid_sequence(n: int, rng: random.Random) -> Seq:
    seq = [label for label in range(1, n + 1) for _ in range(2)]
    rng.shuffle(seq)
    return seq


def seeded_pair(n: int, rng: random.Random) -> tuple[Seq, Seq, str]:
    h = random_valid_sequence(n, rng)
    v = random_valid_sequence(n, rng)
    generator = "random_endpoint_sequences"
    return canonicalize_pair(h, v) + (generator,)


def depth_weighted_lift(h_seq: Seq, v_seq: Seq, n_new: int, rng: random.Random) -> tuple[Seq, Seq]:
    n_old = max(h_seq, default=0)
    h, v = h_seq[:], v_seq[:]
    if n_new <= n_old:
        return canonicalize_pair(h, v)

    def depth(seq: Seq) -> list[int]:
        line = [0] * (len(seq) + 1)
        for left, right in seq_spans(seq):
            line[left] += 1
            if right + 1 < len(line):
                line[right + 1] -= 1
        out: list[int] = []
        current = 0
        for idx in range(len(seq)):
            current += line[idx]
            out.append(current)
        return out

    def weighted_index(weights: list[int]) -> int:
        total = sum(weight + 1 for weight in weights)
        target = rng.randrange(max(1, total))
        prefix = 0
        for idx, weight in enumerate(weights):
            prefix += weight + 1
            if target < prefix:
                return idx
        return max(0, len(weights) - 1)

    for label in range(n_old + 1, n_new + 1):
        for seq in (h, v):
            weights = depth(seq)
            pos = weighted_index(weights)
            seq.insert(pos, label)
            seq.insert(min(pos + 1, len(seq)), label)
    return canonicalize_pair(h, v)


def mutate_pair(
    h_seq: Seq,
    v_seq: Seq,
    rng: random.Random,
    *,
    n_max: int,
    allow_lift: bool,
    strong: bool = False,
) -> tuple[Seq, Seq, str]:
    h, v = h_seq[:], v_seq[:]
    n = max(h, default=0)
    moves = ["swap_h", "swap_v", "move_h", "move_v", "block_h", "block_v", "reverse_h", "reverse_v", "pair_h", "pair_v", "pair_hv"]
    if allow_lift and n < n_max:
        moves.extend(["lift"] * (2 if strong else 1))
    if strong:
        moves.extend(["block_h", "block_v", "reverse_h", "reverse_v", "pair_hv"])
    move = rng.choice(moves)

    if move == "lift":
        h, v = depth_weighted_lift(h, v, min(n_max, n + 1), rng)
        return h, v, "sequence_lift"

    side = h if move.endswith("_h") else v
    if move == "pair_hv":
        labels = sorted(set(h) & set(v))
        if len(labels) >= 2:
            a, b = rng.sample(labels, 2)
            for seq in (h, v):
                for idx, label in enumerate(seq):
                    if label == a:
                        seq[idx] = b
                    elif label == b:
                        seq[idx] = a
        return canonicalize_pair(h, v) + ("paired_label_swap_hv",)

    if len(side) < 2:
        return canonicalize_pair(h, v) + ("noop",)
    i, j = rng.randrange(len(side)), rng.randrange(len(side))
    lo, hi = min(i, j), max(i, j)
    if move.startswith("swap"):
        side[i], side[j] = side[j], side[i]
    elif move.startswith("move") and i != j:
        label = side.pop(i)
        side.insert(j, label)
    elif move.startswith("block") and lo != hi:
        block = side[lo : hi + 1]
        del side[lo : hi + 1]
        target = rng.randrange(len(side) + 1)
        side[target:target] = block
    elif move.startswith("reverse") and lo != hi:
        side[lo : hi + 1] = reversed(side[lo : hi + 1])
    elif move.startswith("pair"):
        labels = sorted(set(side))
        if len(labels) >= 2:
            a, b = rng.sample(labels, 2)
            for idx, label in enumerate(side):
                if label == a:
                    side[idx] = b
                elif label == b:
                    side[idx] = a
    h, v = canonicalize_pair(h, v)
    return h, v, move


def payload_for_pair(h_seq: Seq, v_seq: Seq, *, generator: str, mutation: str | None = None) -> dict[str, Any]:
    rects = rectangles_from_pair(h_seq, v_seq)
    payload: dict[str, Any] = {
        "generator": generator,
        "H": h_seq,
        "V": v_seq,
        "n": max(h_seq, default=0),
        "coordinate_model": "double_occurrence_endpoint_order",
        "rectangles_from_sequences": True,
        "grid_width": 2 * max(h_seq, default=0),
        "edge_order_search": True,
    }
    if mutation:
        payload["last_sequence_mutation"] = mutation
    if rects:
        payload["x_span"] = max(rect[1] for rect in rects) - min(rect[0] for rect in rects)
        payload["y_span"] = max(rect[3] for rect in rects) - min(rect[2] for rect in rects)
    return payload
