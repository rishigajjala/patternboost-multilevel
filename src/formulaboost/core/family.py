from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from formulaboost.core.objects import MathObject
from formulaboost.domains.c4_free_circulant import C4FreeCirculantDomain
from formulaboost.domains.modular_sidon import ModularSidonDomain
from formulaboost.dsl.ast import AstNode
from formulaboost.dsl.complexity import complexity as ast_complexity
from formulaboost.dsl.interpreter import evaluate_modular_set
from formulaboost.dsl.pretty import pretty as ast_pretty


@dataclass(frozen=True)
class FamilyProgram:
    ast: AstNode
    domain: str
    program_id: str = ""
    description: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def evaluate(self, params: dict[str, Any]) -> MathObject:
        n = int(params["n"])
        if self.domain == "modular_sidon":
            domain = ModularSidonDomain()
            if self.ast.op == "greedy_complete":
                base = evaluate_modular_set(self.ast.args["base"], params)
                return domain.greedy_complete(
                    n,
                    base,
                    [*sorted(base), *range(n)],
                    source="family_program",
                    metadata={"program_id": self.program_id},
                )
            elements = evaluate_modular_set(self.ast, params)
            return domain.object_from_elements(
                n,
                elements,
                source="family_program",
                metadata={"program_id": self.program_id},
            )

        if self.domain == "c4_free_circulant":
            domain = C4FreeCirculantDomain()
            if self.ast.op == "greedy_complete":
                base = evaluate_modular_set(self.ast.args["base"], params)
                return domain.greedy_complete(
                    n,
                    base,
                    [*sorted(base), *range(1, n)],
                    source="family_program",
                    metadata={"program_id": self.program_id},
                )
            diffs = evaluate_modular_set(self.ast, params)
            return domain.object_from_diffs(
                n,
                diffs,
                source="family_program",
                metadata={"program_id": self.program_id},
            )

        raise ValueError(f"unsupported FormulaBoost family domain: {self.domain}")

    def complexity(self) -> int:
        return ast_complexity(self.ast)

    def pretty(self) -> str:
        return self.description or ast_pretty(self.ast)

    def with_id(self, program_id: str) -> "FamilyProgram":
        return FamilyProgram(
            ast=self.ast,
            domain=self.domain,
            program_id=program_id,
            description=self.description,
            provenance=self.provenance,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "domain": self.domain,
            "program": self.ast.to_dict(),
            "pretty": self.pretty(),
            "complexity": self.complexity(),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "FamilyProgram":
        ast_row = row.get("program") or row.get("ast")
        if not isinstance(ast_row, dict):
            raise ValueError(f"family program is missing a program AST: {row!r}")
        return cls(
            ast=AstNode.from_dict(ast_row),
            domain=str(row["domain"]),
            program_id=str(row.get("program_id") or ""),
            description=str(row.get("pretty") or row.get("description") or ""),
            provenance=dict(row.get("provenance") or {}),
        )
