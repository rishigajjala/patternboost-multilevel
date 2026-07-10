from __future__ import annotations

from random import Random

from formulaboost.core.evaluator import FamilyEvaluator
from formulaboost.core.family import FamilyProgram
from formulaboost.core.objects import MathObject
from formulaboost.domains.c4_free_circulant import C4FreeCirculantDomain, symmetric_closure
from formulaboost.dsl.ast import AstNode


def test_symmetric_closure_removes_zero_and_adds_negatives():
    assert symmetric_closure(7, [0, 1, 2]) == [1, 2, 5, 6]


def test_c4_free_circulant_verifier_accepts_cycle5_and_rejects_cycle4():
    domain = C4FreeCirculantDomain()
    assert domain.validate(domain.object_from_diffs(5, [1]))
    assert not domain.validate(MathObject("c4_free_circulant", {"n": 4}, {"diffs": [1, 3]}))


def test_c4_free_circulant_two_independent_generators_force_c4():
    domain = C4FreeCirculantDomain()
    for n in range(7, 30):
        assert not domain.validate(domain.object_from_diffs(n, [1, 2]))


def test_c4_canonicalization_is_unit_invariant():
    domain = C4FreeCirculantDomain()
    base = domain.object_from_diffs(13, [1, 5])
    transformed = domain.object_from_diffs(13, [(3 * d) % 13 for d in [1, 5]])
    assert domain.canonicalize(base) == domain.canonicalize(transformed)


def test_c4_greedy_and_family_evaluation_produce_valid_graphs():
    domain = C4FreeCirculantDomain()
    greedy = domain.greedy_object({"n": 17}, Random(0))
    assert greedy.valid is True

    ast = AstNode("greedy_complete", {"base": AstNode("residue_classes", {"modulus": 5, "residues": [1]})})
    program = FamilyProgram(ast=ast, domain="c4_free_circulant", program_id="c4_test")
    result = FamilyEvaluator().evaluate(
        program,
        domain,
        train_params=[{"n": 17}],
        val_params=[{"n": 19}],
        test_params=[{"n": 23}],
    )
    assert result.invalid_count == 0
    assert result.val_mean_score > 0
