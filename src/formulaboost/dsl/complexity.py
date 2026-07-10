from __future__ import annotations

from formulaboost.dsl.ast import AstNode


def complexity(node: AstNode) -> int:
    child_cost = 0
    const_cost = 0
    for value in node.args.values():
        if isinstance(value, AstNode):
            child_cost += complexity(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, AstNode):
                    child_cost += complexity(item)
                else:
                    const_cost += 1
        elif isinstance(value, dict):
            const_cost += len(value)
        else:
            const_cost += 1
    repair_cost = 5 if node.op == "greedy_complete" else 0
    return 1 + child_cost + 2 * const_cost + repair_cost
