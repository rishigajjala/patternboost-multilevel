from __future__ import annotations

from formulaboost.dsl.ast import AstNode


def pretty(node: AstNode) -> str:
    if node.op == "empty_set":
        return "{}"
    if node.op == "finite_set_mod":
        elements = ", ".join(str(x) for x in node.args.get("elements", []))
        return "{" + elements + "} mod n"
    if node.op == "residue_classes":
        modulus = int(node.args["modulus"])
        residues = ", ".join(str(x) for x in sorted(int(r) % modulus for r in node.args.get("residues", [])))
        return f"{{x in Z_n : x mod {modulus} in {{{residues}}}}}"
    if node.op == "set_comprehension":
        var_name = str(node.args.get("var", "x"))
        expr = _pretty_expr(node.args.get("expr", AstNode("var", {"name": var_name})))
        predicate = _pretty_predicate(node.args.get("predicate", AstNode("true")))
        if predicate == "true":
            return f"{{{expr} : {var_name} in Z_n}}"
        return f"{{{expr} : {var_name} in Z_n, {predicate}}}"
    if node.op == "quadratic_residues":
        if node.args.get("include_zero", True):
            return "{x^2 mod n : x in Z_n}"
        return "{x^2 mod n : x in Z_n, x != 0}"
    if node.op == "units_mod":
        return "{x in Z_n : gcd(x,n)=1}"
    if node.op == "union":
        return " union ".join(pretty(child) for child in node.args.get("children", []))
    if node.op == "intersection":
        return " intersection ".join(pretty(child) for child in node.args.get("children", []))
    if node.op == "difference":
        return f"({pretty(node.args['left'])}) \\ ({pretty(node.args['right'])})"
    if node.op == "translate_mod":
        return f"{pretty(node.args['base'])} + {int(node.args.get('shift', 0))} mod n"
    if node.op == "multiply_mod":
        return f"{int(node.args.get('factor', 1))} * ({pretty(node.args['base'])}) mod n"
    if node.op == "greedy_complete":
        return f"greedy_complete({pretty(node.args['base'])})"
    return f"{node.op}(...)"


def _pretty_expr(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if not isinstance(value, AstNode):
        return str(value)
    if value.op == "const":
        return str(value.args["value"])
    if value.op == "var":
        return str(value.args.get("name", "x"))
    if value.op == "param":
        return str(value.args["name"])
    if value.op == "add":
        return " + ".join(_pretty_expr(item) for item in value.args.get("terms", []))
    if value.op == "sub":
        return f"{_pretty_expr(value.args['left'])} - {_pretty_expr(value.args['right'])}"
    if value.op == "mul":
        return " * ".join(_pretty_expr(item) for item in value.args.get("factors", []))
    if value.op == "neg":
        return f"-{_pretty_expr(value.args['value'])}"
    if value.op == "pow":
        return f"{_pretty_expr(value.args['base'])}^{_pretty_expr(value.args['exponent'])}"
    if value.op == "mod":
        return f"{_pretty_expr(value.args['value'])} mod {_pretty_expr(value.args['modulus'])}"
    if value.op == "floor_div":
        return f"{_pretty_expr(value.args['left'])} // {_pretty_expr(value.args['right'])}"
    return f"{value.op}(...)"


def _pretty_predicate(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if not isinstance(value, AstNode):
        return str(value)
    if value.op == "true":
        return "true"
    if value.op == "false":
        return "false"
    if value.op in {"eq", "neq", "lt", "leq", "gt", "geq"}:
        symbols = {"eq": "=", "neq": "!=", "lt": "<", "leq": "<=", "gt": ">", "geq": ">="}
        return f"{_pretty_expr(value.args['left'])} {symbols[value.op]} {_pretty_expr(value.args['right'])}"
    if value.op == "and":
        return " and ".join(_pretty_predicate(item) for item in value.args.get("children", []))
    if value.op == "or":
        return " or ".join(_pretty_predicate(item) for item in value.args.get("children", []))
    if value.op == "not":
        return f"not ({_pretty_predicate(value.args['child'])})"
    if value.op == "in_set":
        options = ", ".join(_pretty_expr(option) for option in value.args.get("options", []))
        return f"{_pretty_expr(value.args['value'])} in {{{options}}}"
    if value.op == "gcd_eq_1":
        return f"gcd({_pretty_expr(value.args['value'])}, n)=1"
    if value.op == "is_unit_mod":
        return f"{_pretty_expr(value.args.get('value', AstNode('var', {'name': 'x'})))} is a unit mod n"
    if value.op == "is_square_mod":
        return f"{_pretty_expr(value.args.get('value', AstNode('var', {'name': 'x'})))} is a square mod n"
    return f"{value.op}(...)"
