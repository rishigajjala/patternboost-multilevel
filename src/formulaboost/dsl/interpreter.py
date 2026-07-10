from __future__ import annotations

from math import gcd
from typing import Any

from formulaboost.dsl.ast import AstNode


def evaluate_modular_set(node: AstNode, params: dict[str, Any]) -> set[int]:
    n = int(params["n"])
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")

    if node.op == "empty_set":
        return set()
    if node.op == "finite_set_mod":
        return {int(x) % n for x in node.args.get("elements", [])}
    if node.op == "residue_classes":
        modulus = int(node.args["modulus"])
        residues = {int(r) % modulus for r in node.args.get("residues", [])}
        return {x for x in range(n) if x % modulus in residues}
    if node.op == "set_comprehension":
        var_name = str(node.args.get("var", "x"))
        domain_name = str(node.args.get("domain", "Z_n"))
        if domain_name != "Z_n":
            raise ValueError(f"unsupported set-comprehension domain: {domain_name!r}")
        expr = node.args.get("expr", AstNode("var", {"name": var_name}))
        predicate = node.args.get("predicate", AstNode("true"))
        result: set[int] = set()
        for x in range(n):
            env = {var_name: x}
            if evaluate_predicate(predicate, params, env):
                result.add(evaluate_int_expr(expr, params, env) % n)
        return result
    if node.op == "quadratic_residues":
        include_zero = bool(node.args.get("include_zero", True))
        residues = {(x * x) % n for x in range(n)}
        if not include_zero:
            residues.discard(0)
        return residues
    if node.op == "units_mod":
        return {x for x in range(n) if gcd(x, n) == 1}
    if node.op == "union":
        result: set[int] = set()
        for child in node.args.get("children", []):
            result.update(evaluate_modular_set(child, params))
        return result
    if node.op == "intersection":
        children = list(node.args.get("children", []))
        if not children:
            return set()
        result = evaluate_modular_set(children[0], params)
        for child in children[1:]:
            result &= evaluate_modular_set(child, params)
        return result
    if node.op == "difference":
        left = evaluate_modular_set(node.args["left"], params)
        right = evaluate_modular_set(node.args["right"], params)
        return left - right
    if node.op == "translate_mod":
        base = evaluate_modular_set(node.args["base"], params)
        shift = int(node.args.get("shift", 0))
        return {(x + shift) % n for x in base}
    if node.op == "multiply_mod":
        base = evaluate_modular_set(node.args["base"], params)
        factor = int(node.args.get("factor", 1))
        return {(factor * x) % n for x in base}
    if node.op == "greedy_complete":
        return evaluate_modular_set(node.args["base"], params)

    raise ValueError(f"unsupported modular set DSL op: {node.op}")


def evaluate_int_expr(value: Any, params: dict[str, Any], env: dict[str, int]) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value in env:
            return int(env[value])
        if value in params:
            return int(params[value])
        return int(value)
    if not isinstance(value, AstNode):
        return int(value)

    if value.op == "const":
        return int(value.args["value"])
    if value.op == "var":
        return int(env[str(value.args.get("name", "x"))])
    if value.op == "param":
        return int(params[str(value.args["name"])])
    if value.op == "add":
        return sum(evaluate_int_expr(item, params, env) for item in value.args.get("terms", []))
    if value.op == "sub":
        return evaluate_int_expr(value.args["left"], params, env) - evaluate_int_expr(value.args["right"], params, env)
    if value.op == "mul":
        result = 1
        for item in value.args.get("factors", []):
            result *= evaluate_int_expr(item, params, env)
        return result
    if value.op == "neg":
        return -evaluate_int_expr(value.args["value"], params, env)
    if value.op == "pow":
        return evaluate_int_expr(value.args["base"], params, env) ** evaluate_int_expr(value.args["exponent"], params, env)
    if value.op == "mod":
        modulus = evaluate_int_expr(value.args["modulus"], params, env)
        return evaluate_int_expr(value.args["value"], params, env) % modulus
    if value.op == "floor_div":
        return evaluate_int_expr(value.args["left"], params, env) // evaluate_int_expr(value.args["right"], params, env)

    raise ValueError(f"unsupported integer DSL expression op: {value.op}")


def evaluate_predicate(value: Any, params: dict[str, Any], env: dict[str, int]) -> bool:
    n = int(params["n"])
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if not isinstance(value, AstNode):
        return bool(value)

    if value.op == "true":
        return True
    if value.op == "false":
        return False
    if value.op == "eq":
        return evaluate_int_expr(value.args["left"], params, env) == evaluate_int_expr(value.args["right"], params, env)
    if value.op == "neq":
        return evaluate_int_expr(value.args["left"], params, env) != evaluate_int_expr(value.args["right"], params, env)
    if value.op == "lt":
        return evaluate_int_expr(value.args["left"], params, env) < evaluate_int_expr(value.args["right"], params, env)
    if value.op == "leq":
        return evaluate_int_expr(value.args["left"], params, env) <= evaluate_int_expr(value.args["right"], params, env)
    if value.op == "gt":
        return evaluate_int_expr(value.args["left"], params, env) > evaluate_int_expr(value.args["right"], params, env)
    if value.op == "geq":
        return evaluate_int_expr(value.args["left"], params, env) >= evaluate_int_expr(value.args["right"], params, env)
    if value.op == "and":
        return all(evaluate_predicate(item, params, env) for item in value.args.get("children", []))
    if value.op == "or":
        return any(evaluate_predicate(item, params, env) for item in value.args.get("children", []))
    if value.op == "not":
        return not evaluate_predicate(value.args["child"], params, env)
    if value.op == "in_set":
        item = evaluate_int_expr(value.args["value"], params, env)
        options = {evaluate_int_expr(option, params, env) for option in value.args.get("options", [])}
        return item in options
    if value.op == "gcd_eq_1":
        return gcd(evaluate_int_expr(value.args["value"], params, env), n) == 1
    if value.op == "is_unit_mod":
        return gcd(evaluate_int_expr(value.args.get("value", AstNode("var", {"name": "x"})), params, env), n) == 1
    if value.op == "is_square_mod":
        target = evaluate_int_expr(value.args.get("value", AstNode("var", {"name": "x"})), params, env) % n
        return target in {(x * x) % n for x in range(n)}

    raise ValueError(f"unsupported boolean DSL predicate op: {value.op}")
