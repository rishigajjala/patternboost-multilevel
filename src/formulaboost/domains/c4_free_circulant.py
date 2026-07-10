from __future__ import annotations

from collections import Counter
from math import gcd, sqrt
from random import Random
from typing import Any, Iterable

from formulaboost.core.objects import MathObject


class C4FreeCirculantDomain:
    name = "c4_free_circulant"

    def object_from_diffs(
        self,
        n: int,
        diffs: Iterable[int],
        *,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MathObject:
        data = {"diffs": symmetric_closure(n, diffs)}
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
        n, diffs = self._n_diffs(obj)
        diff_set = set(diffs)
        if 0 in diff_set:
            return False
        if diff_set != set(symmetric_closure(n, diff_set)):
            return False
        for delta in range(1, n):
            common = 0
            for d in diff_set:
                if (d - delta) % n in diff_set:
                    common += 1
                    if common >= 2:
                        return False
        return True

    def score(self, obj: MathObject) -> float:
        _, diffs = self._n_diffs(obj)
        if self.validate(obj):
            return float(len(diffs))
        return float(len(diffs) - self.violation_count(obj))

    def normalize_score(self, score: float, params: dict[str, Any]) -> float:
        n = max(1, int(params["n"]))
        return float(score) / sqrt(n)

    def random_object(self, params: dict[str, Any], rng: Random) -> MathObject:
        n = int(params["n"])
        candidates = self._generator_representatives(n)
        rng.shuffle(candidates)
        selected: list[int] = []
        for d in candidates:
            if rng.random() < 0.65 and self.is_safe_addition(n, selected, d):
                selected.append(d)
        return self.object_from_diffs(n, selected, source="random_valid")

    def greedy_object(self, params: dict[str, Any], rng: Random) -> MathObject:
        n = int(params["n"])
        order = self._generator_representatives(n)
        rng.shuffle(order)
        return self.greedy_complete(n, [], order, source="greedy")

    def local_repair(self, obj: MathObject, budget: int, rng: Random) -> MathObject:
        n, diffs = self._n_diffs(obj)
        selected = self._to_representatives(n, diffs)
        steps = 0
        while steps < budget and not self.validate(self._raw_object(n, selected)):
            blame = self._duplicate_common_neighbor_blame(n, symmetric_closure(n, selected))
            if not blame:
                break
            worst_count = max(blame.values())
            worst = [d for d in selected if blame[d] == worst_count or blame[(-d) % n] == worst_count]
            if not worst:
                worst = list(selected)
            selected.remove(rng.choice(sorted(worst)))
            steps += 1
        order = self._generator_representatives(n)
        rng.shuffle(order)
        return self.greedy_complete(
            n,
            selected,
            order,
            source="local_repair",
            metadata={"repair_steps": steps, "budget": budget},
        )

    def greedy_complete(
        self,
        n: int,
        seed_diffs: Iterable[int],
        order: Iterable[int] | None = None,
        *,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MathObject:
        selected: list[int] = []
        for d in self._to_representatives(n, seed_diffs):
            if self.is_safe_addition(n, selected, d):
                selected.append(d)
        seen = set(selected)
        candidates = self._generator_representatives(n) if order is None else [self._representative(n, d) for d in order]
        for d in candidates:
            if d not in seen and self.is_safe_addition(n, selected, d):
                selected.append(d)
                seen.add(d)
        return self.object_from_diffs(n, selected, source=source, metadata=metadata)

    def is_safe_addition(self, n: int, diffs: Iterable[int], candidate: int) -> bool:
        reps = self._to_representatives(n, diffs)
        d = self._representative(n, candidate)
        if d == 0 or d in reps:
            return False
        return self.validate(self._raw_object(n, [*reps, d]))

    def canonicalize(self, obj: MathObject) -> str:
        n, diffs = self._n_diffs(obj)
        units = [u for u in range(n) if gcd(u, n) == 1]
        best: tuple[int, ...] | None = None
        for unit in units:
            transformed = tuple(sorted((unit * d) % n for d in diffs))
            if best is None or transformed < best:
                best = transformed
        text = ",".join(str(x) for x in best or ())
        return f"c4circ:n={n}:{text}"

    def invariants(self, obj: MathObject) -> dict[str, Any]:
        n, diffs = self._n_diffs(obj)
        diff_set = set(diffs)
        common_neighbor_counts = [
            sum(1 for d in diff_set if (d - delta) % n in diff_set)
            for delta in range(1, n)
        ]
        residue_profile = {
            str(m): [sum(1 for x in diffs if x % m == r) for r in range(m)]
            for m in range(2, min(9, n + 1))
        }
        return {
            "n": n,
            "degree": len(diffs),
            "edges": n * len(diffs) // 2,
            "max_common_neighbors": max(common_neighbor_counts, default=0),
            "residue_profile": residue_profile,
        }

    def similarity(self, obj_a: MathObject, obj_b: MathObject) -> float:
        _, a = self._n_diffs(obj_a)
        _, b = self._n_diffs(obj_b)
        set_a = set(a)
        set_b = set(b)
        if not set_a and not set_b:
            return 1.0
        return len(set_a & set_b) / len(set_a | set_b)

    def violation_count(self, obj: MathObject) -> int:
        n, diffs = self._n_diffs(obj)
        diff_set = set(diffs)
        violations = 0
        for delta in range(1, n):
            common = sum(1 for d in diff_set if (d - delta) % n in diff_set)
            violations += max(0, common - 1)
        return violations

    def _duplicate_common_neighbor_blame(self, n: int, diffs: list[int]) -> Counter[int]:
        diff_set = set(diffs)
        blame: Counter[int] = Counter()
        for delta in range(1, n):
            witnesses = [d for d in diff_set if (d - delta) % n in diff_set]
            if len(witnesses) > 1:
                for d in witnesses:
                    blame[d] += 1
                    blame[(d - delta) % n] += 1
        return blame

    def _n_diffs(self, obj: MathObject) -> tuple[int, list[int]]:
        if obj.domain != self.name:
            raise ValueError(f"expected domain {self.name!r}, got {obj.domain!r}")
        n = int(obj.params["n"])
        return n, symmetric_closure(n, obj.data.get("diffs", []))

    def _raw_object(self, n: int, diffs: Iterable[int]) -> MathObject:
        return MathObject(domain=self.name, params={"n": n}, data={"diffs": symmetric_closure(n, diffs)})

    def _generator_representatives(self, n: int) -> list[int]:
        return [d for d in range(1, n // 2 + 1) if d % n != 0]

    def _to_representatives(self, n: int, diffs: Iterable[int]) -> list[int]:
        return sorted({self._representative(n, d) for d in diffs if int(d) % n != 0})

    def _representative(self, n: int, d: int) -> int:
        x = int(d) % n
        return min(x, (-x) % n)


def symmetric_closure(n: int, diffs: Iterable[int]) -> list[int]:
    values = set()
    for d in diffs:
        x = int(d) % int(n)
        if x == 0:
            continue
        values.add(x)
        values.add((-x) % int(n))
    return sorted(values)
