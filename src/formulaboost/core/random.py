from __future__ import annotations

from random import Random
from typing import Iterable, TypeVar

T = TypeVar("T")


def seeded_rng(seed: int | None) -> Random:
    return Random(0 if seed is None else int(seed))


def shuffled(values: Iterable[T], seed: int | None) -> list[T]:
    items = list(values)
    seeded_rng(seed).shuffle(items)
    return items
