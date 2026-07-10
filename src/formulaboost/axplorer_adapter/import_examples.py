from __future__ import annotations

from pathlib import Path

from formulaboost.axplorer_adapter.codecs import axplorer_row_to_math_object, read_axplorer_rows
from formulaboost.core.objects import MathObject
from formulaboost.core.serialization import write_math_objects


def import_axplorer_examples(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    domain: str | None = None,
) -> list[MathObject]:
    objects = [axplorer_row_to_math_object(row, default_domain=domain) for row in read_axplorer_rows(input_path)]
    if output_path is not None:
        write_math_objects(output_path, objects)
    return objects
