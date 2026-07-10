from __future__ import annotations

import hashlib
import json
from typing import Any

from formulaboost.dsl.ast import AstNode
from formulaboost.dsl.interpreter import evaluate_modular_set


DEFAULT_HASH_PARAMS = [{"n": 11}, {"n": 13}, {"n": 17}]


def semantic_hash(node: AstNode, params_list: list[dict[str, Any]] | None = None) -> str:
    params = params_list or DEFAULT_HASH_PARAMS
    payload = [
        {
            "params": dict(sorted(param.items())),
            "values": sorted(evaluate_modular_set(node, param)),
        }
        for param in params
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def semantically_equivalent(left: AstNode, right: AstNode, params_list: list[dict[str, Any]] | None = None) -> bool:
    return semantic_hash(left, params_list) == semantic_hash(right, params_list)
