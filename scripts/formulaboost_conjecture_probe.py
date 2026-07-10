#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Iterable

from formulaboost.domains.c4_free_circulant import C4FreeCirculantDomain
from formulaboost.domains.modular_sidon import ModularSidonDomain


@dataclass(frozen=True)
class ExactResult:
    n: int
    best_size: int
    witness: tuple[int, ...]
    upper_bound: int
    ratio: float
    singer_order: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "best_size": self.best_size,
            "witness": list(self.witness),
            "upper_bound": self.upper_bound,
            "ratio_best_over_sqrt_n": self.ratio,
            "is_projective_plane_order_q2_q_1": self.singer_order,
        }


def sidon_upper_bound(n: int) -> int:
    # Difference-counting bound: k(k-1) <= n-1.
    return int((1 + math.isqrt(1 + 4 * (n - 1))) // 2)


def is_projective_plane_order(n: int) -> bool:
    # Singer cyclic difference sets have order q^2 + q + 1 for prime powers q.
    for q in range(2, int(math.sqrt(n)) + 2):
        if q * q + q + 1 == n and _is_prime_power(q):
            return True
    return False


def exact_cyclic_sidon(n: int) -> ExactResult:
    best: tuple[int, ...] = (0,)
    candidates = tuple(range(1, n))

    def can_add(selected: tuple[int, ...], used_sums: frozenset[int], x: int) -> frozenset[int] | None:
        new_sums = [(x + x) % n, *((x + a) % n for a in selected)]
        if len(set(new_sums)) != len(new_sums):
            return None
        if any(total in used_sums for total in new_sums):
            return None
        return used_sums | frozenset(new_sums)

    def search(index: int, selected: tuple[int, ...], used_sums: frozenset[int]) -> None:
        nonlocal best
        if len(selected) + (len(candidates) - index) <= len(best):
            return
        if len(selected) > len(best):
            best = selected
        if len(best) >= sidon_upper_bound(n):
            return
        for pos in range(index, len(candidates)):
            x = candidates[pos]
            next_sums = can_add(selected, used_sums, x)
            if next_sums is not None:
                search(pos + 1, (*selected, x), next_sums)

    search(0, (0,), frozenset({0}))
    return ExactResult(
        n=n,
        best_size=len(best),
        witness=best,
        upper_bound=sidon_upper_bound(n),
        ratio=len(best) / math.sqrt(n),
        singer_order=is_projective_plane_order(n),
    )


def exact_c4_circulant(n: int) -> ExactResult:
    domain = C4FreeCirculantDomain()
    reps = tuple(range(1, n // 2 + 1))
    best: tuple[int, ...] = ()

    def search(index: int, selected: tuple[int, ...]) -> None:
        nonlocal best
        if 2 * (len(selected) + (len(reps) - index)) <= len(best):
            return
        if 2 * len(selected) > len(best):
            obj = domain.object_from_diffs(n, selected)
            if obj.valid:
                best = tuple(obj.data["diffs"])
        for pos in range(index, len(reps)):
            candidate = reps[pos]
            if domain.is_safe_addition(n, selected, candidate):
                search(pos + 1, (*selected, candidate))

    search(0, ())
    return ExactResult(
        n=n,
        best_size=len(best),
        witness=best,
        upper_bound=sidon_upper_bound(n),
        ratio=len(best) / math.sqrt(n),
        singer_order=is_projective_plane_order(n),
    )


def greedy_sidon(n: int, restarts: int, rng: Random) -> tuple[int, ...]:
    domain = ModularSidonDomain()
    best: tuple[int, ...] = ()
    for _ in range(restarts):
        obj = domain.greedy_object({"n": n}, rng)
        witness = tuple(obj.data["elements"])
        if len(witness) > len(best):
            best = witness
    return best


def _is_prime_power(q: int) -> bool:
    if q < 2:
        return False
    for p in range(2, q + 1):
        if q % p != 0 or not _is_prime(p):
            continue
        value = q
        while value % p == 0:
            value //= p
        if value == 1:
            return True
    return False


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for d in range(2, int(math.sqrt(n)) + 1):
        if n % d == 0:
            return False
    return True


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    sidon_rows = payload["cyclic_sidon_exact"]
    c4_rows = payload["c4_circulant_exact"]
    lines = [
        "# FormulaBoost Conjecture Probe",
        "",
        "This is a finite counterexample search, not a proof. It targets conjecture-adjacent structure relevant to FormulaBoost's current domains.",
        "",
        "## Cyclic Sidon Exact Search",
        "",
        "| n | best | bound | best/sqrt(n) | projective-plane order | witness |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for row in sidon_rows:  # type: ignore[union-attr]
        lines.append(
            f"| {row['n']} | {row['best_size']} | {row['upper_bound']} | "
            f"{row['ratio_best_over_sqrt_n']:.3f} | {row['is_projective_plane_order_q2_q_1']} | "
            f"`{row['witness']}` |"
        )
    lines.extend(
        [
            "",
            "## C4-Free Circulant Exact Search",
            "",
            "Breaker note: this domain is degenerate for undirected abelian circulants. If the symmetric difference set contains two distinct inverse-pair generators `±a` and `±b`, then `0, a, a+b, b` is a 4-cycle. The exact search below is consistent with the stronger theorem that C4-free circulants have degree at most 2.",
            "",
            "| n | best degree | bound proxy | degree/sqrt(n) | witness diffs |",
            "|---:|---:|---:|---:|---|",
        ]
    )
    for row in c4_rows:  # type: ignore[union-attr]
        lines.append(
            f"| {row['n']} | {row['best_size']} | {row['upper_bound']} | "
            f"{row['ratio_best_over_sqrt_n']:.3f} | `{row['witness']}` |"
        )
    lines.extend(
        [
            "",
            "## Greedy Larger-N Sidon Smoke",
            "",
            "| n | best found | best/sqrt(n) | witness |",
            "|---:|---:|---:|---|",
        ]
    )
    for row in payload["cyclic_sidon_greedy"]:  # type: ignore[index]
        lines.append(
            f"| {row['n']} | {row['best_size']} | {row['ratio_best_over_sqrt_n']:.3f} | `{row['witness']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    sidon_exact = [exact_cyclic_sidon(n).to_dict() for n in range(args.sidon_min_n, args.sidon_max_n + 1)]
    c4_exact = [exact_c4_circulant(n).to_dict() for n in range(args.c4_min_n, args.c4_max_n + 1)]
    rng = Random(args.seed)
    sidon_greedy = []
    for n in args.greedy_n:
        witness = greedy_sidon(n, args.greedy_restarts, rng)
        sidon_greedy.append(
            {
                "n": n,
                "best_size": len(witness),
                "witness": list(witness),
                "ratio_best_over_sqrt_n": len(witness) / math.sqrt(n),
            }
        )
    return {
        "schema": "formulaboost_conjecture_probe_v1",
        "seed": args.seed,
        "cyclic_sidon_exact": sidon_exact,
        "c4_circulant_exact": c4_exact,
        "cyclic_sidon_greedy": sidon_greedy,
        "notes": [
            "No finite result here disproves an asymptotic conjecture by itself.",
            "Rows with high Sidon ratio at non-projective-plane orders are leads for structure mining, not counterexamples to the dense-Sidon conjecture.",
            "The C4-free circulant target is degenerate for undirected abelian circulants: two distinct inverse-pair generators force the 4-cycle 0-a-(a+b)-b-0.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sidon-min-n", type=int, default=7)
    parser.add_argument("--sidon-max-n", type=int, default=55)
    parser.add_argument("--c4-min-n", type=int, default=5)
    parser.add_argument("--c4-max-n", type=int, default=45)
    parser.add_argument("--greedy-n", type=int, nargs="+", default=[101, 127, 151, 181])
    parser.add_argument("--greedy-restarts", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="runs/formulaboost_conjectures/probe.json")
    args = parser.parse_args()
    payload = run_probe(args)
    out = Path(args.out)
    _write_json(out, payload)
    _write_markdown(out.with_suffix(".md"), payload)
    sidon_best = max(payload["cyclic_sidon_exact"], key=lambda row: row["ratio_best_over_sqrt_n"])  # type: ignore[index]
    c4_best = max(payload["c4_circulant_exact"], key=lambda row: row["ratio_best_over_sqrt_n"])  # type: ignore[index]
    print(f"wrote {out} and {out.with_suffix('.md')}")
    print(f"best exact Sidon ratio: n={sidon_best['n']} size={sidon_best['best_size']} ratio={sidon_best['ratio_best_over_sqrt_n']:.3f}")
    print(f"best exact C4 circulant ratio: n={c4_best['n']} degree={c4_best['best_size']} ratio={c4_best['ratio_best_over_sqrt_n']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
