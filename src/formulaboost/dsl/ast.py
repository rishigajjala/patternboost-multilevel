from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AstNode:
    op: str
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        encoded: dict[str, Any] = {"type": self.op}
        for key, value in self.args.items():
            encoded[key] = _encode(value)
        return encoded

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "AstNode":
        if "type" not in row:
            raise ValueError(f"DSL AST node is missing type: {row!r}")
        args = {key: _decode(value) for key, value in row.items() if key != "type"}
        return cls(op=str(row["type"]), args=args)

    def stable_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def ast_from_dict(row: dict[str, Any]) -> AstNode:
    return AstNode.from_dict(row)


def _encode(value: Any) -> Any:
    if isinstance(value, AstNode):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, set):
        return sorted(_encode(item) for item in value)
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and "type" in value:
        return AstNode.from_dict(value)
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        return {key: _decode(item) for key, item in value.items()}
    return value
