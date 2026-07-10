from __future__ import annotations

from formulaboost.core.random import seeded_rng, shuffled
from formulaboost.dsl.ast import AstNode
from formulaboost.dsl.interpreter import evaluate_modular_set
from formulaboost.dsl.pretty import pretty
from formulaboost.dsl.semantic_hash import semantic_hash, semantically_equivalent


def test_seeded_rng_and_shuffled_are_deterministic():
    assert [seeded_rng(7).randrange(100) for _ in range(3)] == [41, 41, 41]
    assert shuffled(range(6), 10) == shuffled(range(6), 10)


def test_set_comprehension_over_zn_matches_residue_classes():
    comprehension = AstNode(
        "set_comprehension",
        {
            "var": "x",
            "domain": "Z_n",
            "expr": AstNode("var", {"name": "x"}),
            "predicate": AstNode(
                "in_set",
                {
                    "value": AstNode("mod", {"value": AstNode("var", {"name": "x"}), "modulus": 5}),
                    "options": [1, 4],
                },
            ),
        },
    )
    residue = AstNode("residue_classes", {"modulus": 5, "residues": [1, 4]})
    assert evaluate_modular_set(comprehension, {"n": 17}) == evaluate_modular_set(residue, {"n": 17})
    assert "x in Z_n" in pretty(comprehension)
    assert semantically_equivalent(comprehension, residue, [{"n": 17}, {"n": 19}])


def test_semantic_hash_separates_different_programs():
    left = AstNode("residue_classes", {"modulus": 3, "residues": [0]})
    right = AstNode("residue_classes", {"modulus": 3, "residues": [1]})
    assert semantic_hash(left, [{"n": 17}]) != semantic_hash(right, [{"n": 17}])
