from __future__ import annotations

from collections import defaultdict
from random import Random

from formulaboost.core.domain import Domain
from formulaboost.core.family import FamilyProgram
from formulaboost.core.objects import MathObject
from formulaboost.dsl.ast import AstNode


class ResidueFrequencyMiner:
    name = "residue_frequency"

    def __init__(self, max_modulus: int = 12, threshold: float = 1.15) -> None:
        self.max_modulus = int(max_modulus)
        self.threshold = float(threshold)

    def propose(
        self,
        examples: list[MathObject],
        domain: Domain,
        budget: int,
        rng: Random,
    ) -> list[FamilyProgram]:
        del rng
        domain_name = str(domain.name)
        programs: list[FamilyProgram] = [
            _program(domain_name, AstNode("greedy_complete", {"base": AstNode("empty_set")}), "empty-set greedy completion"),
            _program(
                domain_name,
                AstNode("greedy_complete", {"base": AstNode("quadratic_residues", {"include_zero": True})}),
                "quadratic residues plus greedy completion",
            ),
            _program(
                domain_name,
                AstNode("greedy_complete", {"base": AstNode("units_mod")}),
                "units modulo n plus greedy completion",
            ),
        ]

        if examples:
            programs.extend(self._residue_programs(examples, domain_name))

        deduped: list[FamilyProgram] = []
        seen: set[str] = set()
        for program in programs:
            key = program.ast.stable_json()
            if key not in seen:
                seen.add(key)
                deduped.append(program)
            if len(deduped) >= budget:
                break
        return deduped

    def _residue_programs(self, examples: list[MathObject], domain_name: str) -> list[FamilyProgram]:
        programs: list[FamilyProgram] = []
        for modulus in range(2, self.max_modulus + 1):
            counts = defaultdict(int)
            totals = defaultdict(int)
            global_density_num = 0
            global_density_den = 0
            for obj in examples:
                n = int(obj.params["n"])
                values = obj.data.get("elements", obj.data.get("diffs", []))
                elements = {int(x) % n for x in values}
                global_density_num += len(elements)
                global_density_den += n
                for x in range(n):
                    totals[x % modulus] += 1
                    if x in elements:
                        counts[x % modulus] += 1
            baseline = global_density_num / max(1, global_density_den)
            promising = [
                residue
                for residue in range(modulus)
                if totals[residue] and (counts[residue] / totals[residue]) >= self.threshold * baseline
            ]
            if not promising:
                continue
            base = AstNode("residue_classes", {"modulus": modulus, "residues": promising})
            programs.append(
                _program(
                    domain_name,
                    AstNode("greedy_complete", {"base": base}),
                    f"frequent residues mod {modulus} plus greedy completion",
                )
            )
        return programs


def _program(domain_name: str, ast: AstNode, description: str) -> FamilyProgram:
    return FamilyProgram(
        ast=ast,
        domain=domain_name,
        description=description,
        provenance={"miner": ResidueFrequencyMiner.name},
    )
