from __future__ import annotations

from random import Random

from formulaboost.core.evaluator import FamilyEvaluator
from formulaboost.core.family import FamilyProgram
from formulaboost.core.objects import MathObject
from formulaboost.domains.modular_sidon import ModularSidonDomain
from formulaboost.dsl.ast import AstNode


def test_modular_sidon_verifier_accepts_and_rejects_examples():
    domain = ModularSidonDomain()
    assert domain.validate(domain.object_from_elements(7, [0, 1, 3]))
    assert not domain.validate(MathObject("modular_sidon", {"n": 7}, {"elements": [0, 1, 2]}))


def test_modular_sidon_canonicalization_is_affine_invariant():
    domain = ModularSidonDomain()
    base = domain.object_from_elements(11, [0, 1, 3])
    transformed = domain.object_from_elements(11, [(3 * x + 5) % 11 for x in [0, 1, 3]])
    assert domain.canonicalize(base) == domain.canonicalize(transformed)


def test_local_repair_returns_valid_sidon_set():
    domain = ModularSidonDomain()
    bad = MathObject("modular_sidon", {"n": 13}, {"elements": [0, 1, 2, 3, 4, 5]})
    repaired = domain.local_repair(bad, budget=20, rng=Random(0))
    assert repaired.valid is True
    assert domain.validate(repaired)


def test_dsl_ast_round_trip_and_family_evaluation():
    ast = AstNode(
        "greedy_complete",
        {"base": AstNode("residue_classes", {"modulus": 3, "residues": [0, 1]})},
    )
    assert AstNode.from_dict(ast.to_dict()) == ast

    domain = ModularSidonDomain()
    program = FamilyProgram(ast=ast, domain="modular_sidon", program_id="test")
    result = FamilyEvaluator().evaluate(
        program,
        domain,
        train_params=[{"n": 17}],
        val_params=[{"n": 19}],
        test_params=[{"n": 23}],
    )
    assert result.invalid_count == 0
    assert result.train_mean_score > 0
