from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MathObject:
    domain: str
    params: dict[str, Any]
    data: dict[str, Any]
    canonical: str | None = None
    score: float | None = None
    valid: bool | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "params": self.params,
            "data": self.data,
            "canonical": self.canonical,
            "score": self.score,
            "valid": self.valid,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "MathObject":
        return cls(
            domain=str(row["domain"]),
            params=dict(row.get("params") or {}),
            data=dict(row.get("data") or {}),
            canonical=row.get("canonical"),
            score=None if row.get("score") is None else float(row["score"]),
            valid=row.get("valid"),
            source=row.get("source"),
            metadata=dict(row.get("metadata") or {}),
        )
