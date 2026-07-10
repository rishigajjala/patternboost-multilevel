from __future__ import annotations

from pathlib import Path
from typing import Any

from formulaboost.axplorer_adapter.codecs import math_object_to_axplorer_seed
from formulaboost.core.family import FamilyProgram
from formulaboost.core.objects import MathObject
from formulaboost.core.serialization import write_jsonl


def export_math_object_seeds(
    objects: list[MathObject],
    output_path: str | Path,
    *,
    env_name: str | None = None,
) -> Path:
    return write_jsonl(output_path, (math_object_to_axplorer_seed(obj, env_name=env_name) for obj in objects))


def export_family_program_seeds(
    family_rows: list[dict[str, Any]],
    params: dict[str, Any],
    output_path: str | Path,
    *,
    domain: str | None = None,
    top_k: int = 10,
    env_name: str | None = None,
) -> list[MathObject]:
    objects: list[MathObject] = []
    for row in family_rows:
        if domain is not None and row.get("domain") != domain:
            continue
        program = FamilyProgram.from_dict(row)
        objects.append(program.evaluate(params))
        if len(objects) >= top_k:
            break
    export_math_object_seeds(objects, output_path, env_name=env_name)
    return objects
