from __future__ import annotations

from collections import Counter, defaultdict
from math import gcd, sqrt
from random import Random
from typing import Any, Iterable

from formulaboost.core.objects import MathObject


class ModularSidonDomain:
    name = "modular_sidon"

    def object_from_elements(
        self,
        n: int,
        elements: Iterable[int],
        *,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MathObject:
        data = {"elements": normalize_elements(n, elements)}
        obj = MathObject(
            domain=self.name,
            params={"n": int(n)},
            data=data,
            source=source,
            metadata=dict(metadata or {}),
        )
        valid = self.validate(obj)
        score = self.score(obj)
        return MathObject(
            domain=obj.domain,
            params=obj.params,
            data=obj.data,
            canonical=self.canonicalize(obj),
            score=score,
            valid=valid,
            source=obj.source,
            metadata=obj.metadata,
        )

    def validate(self, obj: MathObject) -> bool:
        n, elements = self._n_elements(obj)
        seen: dict[int, tuple[int, int]] = {}
        for i, a in enumerate(elements):
            for b in elements[i:]:
                pair = (a, b)
                total = (a + b) % n
                previous = seen.get(total)
                if previous is not None and previous != pair:
                    return False
                seen[total] = pair
        return True

    def score(self, obj: MathObject) -> float:
        _, elements = self._n_elements(obj)
        if self.validate(obj):
            return float(len(elements))
        return float(len(elements) - self.violation_count(obj))

    def normalize_score(self, score: float, params: dict[str, Any]) -> float:
        n = max(1, int(params["n"]))
        return float(score) / sqrt(n)

    def random_object(self, params: dict[str, Any], rng: Random) -> MathObject:
        n = int(params["n"])
        order = list(range(n))
        rng.shuffle(order)
        selected: list[int] = []
        for x in order:
            if rng.random() < 0.65 and self.is_safe_addition(n, selected, x):
                selected.append(x)
        return self.object_from_elements(n, selected, source="random_valid")

    def greedy_object(self, params: dict[str, Any], rng: Random) -> MathObject:
        n = int(params["n"])
        order = list(range(n))
        rng.shuffle(order)
        return self.greedy_complete(n, [], order, source="greedy")

    def local_repair(self, obj: MathObject, budget: int, rng: Random) -> MathObject:
        n, elements = self._n_elements(obj)
        selected = list(elements)
        steps = 0
        while steps < budget and not self.validate(self._raw_object(n, selected)):
            blame = self._duplicate_sum_blame(n, selected)
            if not blame:
                break
            worst_count = max(blame.values())
            worst = sorted(x for x, count in blame.items() if count == worst_count)
            selected.remove(rng.choice(worst))
            steps += 1
        remaining = list(range(n))
        rng.shuffle(remaining)
        completed = self.greedy_complete(
            n,
            selected,
            remaining,
            source="local_repair",
            metadata={"repair_steps": steps, "budget": budget},
        )
        return completed

    def greedy_complete(
        self,
        n: int,
        seed_elements: Iterable[int],
        order: Iterable[int] | None = None,
        *,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MathObject:
        selected: list[int] = []
        for x in normalize_elements(n, seed_elements):
            if self.is_safe_addition(n, selected, x):
                selected.append(x)
        seen = set(selected)
        candidates = list(range(n)) if order is None else [int(x) % n for x in order]
        for x in candidates:
            if x not in seen and self.is_safe_addition(n, selected, x):
                selected.append(x)
                seen.add(x)
        return self.object_from_elements(n, selected, source=source, metadata=metadata)

    def is_safe_addition(self, n: int, elements: Iterable[int], candidate: int) -> bool:
        normalized = normalize_elements(n, elements)
        x = int(candidate) % n
        if x in normalized:
            return False
        return self.validate(self._raw_object(n, [*normalized, x]))

    def canonicalize(self, obj: MathObject) -> str:
        n, elements = self._n_elements(obj)
        if not elements:
            return f"sidon:n={n}:"
        units = [u for u in range(n) if gcd(u, n) == 1]
        best: tuple[int, ...] | None = None
        for unit in units:
            multiplied = [(unit * x) % n for x in elements]
            for shift in range(n):
                transformed = tuple(sorted((x + shift) % n for x in multiplied))
                if best is None or transformed < best:
                    best = transformed
        text = ",".join(str(x) for x in best or ())
        return f"sidon:n={n}:{text}"

    def invariants(self, obj: MathObject) -> dict[str, Any]:
        n, elements = self._n_elements(obj)
        diff_counts = Counter((a - b) % n for a in elements for b in elements if a != b)
        residue_profile = {
            str(m): [sum(1 for x in elements if x % m == r) for r in range(m)]
            for m in range(2, min(9, n + 1))
        }
        return {
            "size": len(elements),
            "n": n,
            "density": len(elements) / n,
            "max_difference_multiplicity": max(diff_counts.values(), default=0),
            "residue_profile": residue_profile,
        }

    def similarity(self, obj_a: MathObject, obj_b: MathObject) -> float:
        _, a = self._n_elements(obj_a)
        _, b = self._n_elements(obj_b)
        set_a = set(a)
        set_b = set(b)
        if not set_a and not set_b:
            return 1.0
        return len(set_a & set_b) / len(set_a | set_b)

    def violation_count(self, obj: MathObject) -> int:
        n, elements = self._n_elements(obj)
        sums: dict[int, set[tuple[int, int]]] = defaultdict(set)
        for i, a in enumerate(elements):
            for b in elements[i:]:
                sums[(a + b) % n].add((a, b))
        return sum(max(0, len(pairs) - 1) for pairs in sums.values())

    def _duplicate_sum_blame(self, n: int, elements: list[int]) -> Counter[int]:
        sums: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for i, a in enumerate(elements):
            for b in elements[i:]:
                sums[(a + b) % n].append((a, b))
        blame: Counter[int] = Counter()
        for pairs in sums.values():
            if len(pairs) > 1:
                for a, b in pairs:
                    blame[a] += 1
                    blame[b] += 1
        return blame

    def _n_elements(self, obj: MathObject) -> tuple[int, list[int]]:
        if obj.domain != self.name:
            raise ValueError(f"expected domain {self.name!r}, got {obj.domain!r}")
        n = int(obj.params["n"])
        return n, normalize_elements(n, obj.data.get("elements", []))

    def _raw_object(self, n: int, elements: Iterable[int]) -> MathObject:
        return MathObject(domain=self.name, params={"n": n}, data={"elements": normalize_elements(n, elements)})


def normalize_elements(n: int, elements: Iterable[int]) -> list[int]:
    return sorted({int(x) % int(n) for x in elements})
