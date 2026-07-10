from __future__ import annotations

from formulaboost.core.domain import Domain
from formulaboost.domains.c4_free_circulant import C4FreeCirculantDomain
from formulaboost.domains.modular_sidon import ModularSidonDomain


def domain_registry() -> dict[str, Domain]:
    sidon = ModularSidonDomain()
    c4 = C4FreeCirculantDomain()
    return {sidon.name: sidon, c4.name: c4}


def get_domain(name: str) -> Domain:
    registry = domain_registry()
    if name not in registry:
        known = ", ".join(sorted(registry))
        raise KeyError(f"unknown FormulaBoost domain {name!r}; known domains: {known}")
    return registry[name]
