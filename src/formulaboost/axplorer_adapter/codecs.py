from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from formulaboost.core.objects import MathObject
from formulaboost.core.registry import get_domain
from formulaboost.core.serialization import read_jsonl


ENV_TO_DOMAIN = {
    "sidon": "modular_sidon",
    "modular_sidon": "modular_sidon",
    "c4_free_circulant": "c4_free_circulant",
    "c4": "c4_free_circulant",
    "square": "c4_free_circulant",
}

DOMAIN_TO_ENV = {
    "modular_sidon": "modular_sidon",
    "c4_free_circulant": "c4_free_circulant",
}


def read_axplorer_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".jsonl":
        return read_jsonl(source)
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [dict(row) for row in payload]
    if not isinstance(payload, dict):
        raise ValueError(f"unsupported Axplorer payload in {source}")
    for key in ("examples", "population", "seeds", "data", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value]
    return [payload]


def axplorer_row_to_math_object(row: dict[str, Any], default_domain: str | None = None) -> MathObject:
    if "domain" in row and "params" in row and "data" in row:
        return _validated_object(MathObject.from_dict(row))

    env_name = str(row.get("env_name") or row.get("env") or row.get("problem") or default_domain or "")
    domain_name = ENV_TO_DOMAIN.get(env_name, env_name)
    if domain_name not in DOMAIN_TO_ENV:
        raise ValueError(f"cannot map Axplorer environment {env_name!r} to a FormulaBoost domain")

    n_value = row.get("N", row.get("n"))
    if n_value is None and isinstance(row.get("params"), dict):
        n_value = row["params"].get("n", row["params"].get("N"))
    if n_value is None:
        raise ValueError(f"Axplorer row is missing N/n: {row!r}")
    n = int(n_value)

    raw_object = row.get("object", row.get("solution", row.get("data", row.get("values"))))
    if raw_object is None:
        raise ValueError(f"Axplorer row is missing object data: {row!r}")
    if domain_name == "modular_sidon":
        values = raw_object.get("elements") if isinstance(raw_object, dict) else raw_object
        obj = get_domain(domain_name).object_from_elements(  # type: ignore[attr-defined]
            n,
            values,
            source="axplorer",
            metadata=_metadata(row),
        )
    elif domain_name == "c4_free_circulant":
        values = raw_object.get("diffs") if isinstance(raw_object, dict) else raw_object
        obj = get_domain(domain_name).object_from_diffs(  # type: ignore[attr-defined]
            n,
            values,
            source="axplorer",
            metadata=_metadata(row),
        )
    else:  # pragma: no cover - ENV_TO_DOMAIN gates this today
        raise ValueError(f"unsupported FormulaBoost domain: {domain_name}")
    return obj


def math_object_to_axplorer_seed(obj: MathObject, env_name: str | None = None) -> dict[str, Any]:
    env = env_name or DOMAIN_TO_ENV.get(obj.domain, obj.domain)
    if obj.domain == "modular_sidon":
        payload = list(obj.data.get("elements", []))
    elif obj.domain == "c4_free_circulant":
        payload = list(obj.data.get("diffs", []))
    else:
        payload = dict(obj.data)
    return {
        "schema": "axplorer_seed_v1",
        "env_name": env,
        "N": int(obj.params["n"]),
        "object": payload,
        "score": obj.score,
        "valid": obj.valid,
        "source": obj.source or "formulaboost",
        "metadata": dict(obj.metadata),
    }


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    for key in ("score", "valid", "exp_id", "rank", "seed"):
        if key in row:
            metadata[f"axplorer_{key}"] = row[key]
    return metadata


def _validated_object(obj: MathObject) -> MathObject:
    domain = get_domain(obj.domain)
    if obj.domain == "modular_sidon":
        return domain.object_from_elements(  # type: ignore[attr-defined]
            int(obj.params["n"]),
            obj.data.get("elements", []),
            source=obj.source,
            metadata=obj.metadata,
        )
    if obj.domain == "c4_free_circulant":
        return domain.object_from_diffs(  # type: ignore[attr-defined]
            int(obj.params["n"]),
            obj.data.get("diffs", []),
            source=obj.source,
            metadata=obj.metadata,
        )
    return obj
