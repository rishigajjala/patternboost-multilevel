from __future__ import annotations

import json

from formulaboost.axplorer_adapter import import_axplorer_examples
from formulaboost.cli import main


def test_import_axplorer_fixture_converts_to_math_objects():
    objects = import_axplorer_examples("tests/fixtures/axplorer_population.jsonl")
    assert [obj.domain for obj in objects] == ["modular_sidon", "c4_free_circulant"]
    assert objects[0].valid is True
    assert objects[1].data["diffs"] == [1, 4]


def test_import_axplorer_examples_cli_writes_jsonl(tmp_path):
    out = tmp_path / "examples.jsonl"
    code = main(
        [
            "import-axplorer-examples",
            "--input",
            "tests/fixtures/axplorer_population.jsonl",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["domain"] == "modular_sidon"
    assert rows[1]["domain"] == "c4_free_circulant"


def test_export_axplorer_seeds_cli_writes_axplorer_rows(tmp_path):
    families = tmp_path / "families.jsonl"
    family = {
        "program_id": "fb_test",
        "domain": "c4_free_circulant",
        "program": {"type": "greedy_complete", "base": {"type": "empty_set"}},
        "pretty": "greedy_complete({})",
        "complexity": 7,
        "provenance": {"test": True},
    }
    families.write_text(json.dumps(family) + "\n", encoding="utf-8")
    out = tmp_path / "axplorer_seeds.jsonl"
    code = main(
        [
            "export-axplorer-seeds",
            "--families",
            str(families),
            "--domain",
            "c4_free_circulant",
            "--params",
            '{"n":17}',
            "--top-k",
            "1",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert row["schema"] == "axplorer_seed_v1"
    assert row["env_name"] == "c4_free_circulant"
    assert row["N"] == 17
    assert row["valid"] is True
    assert isinstance(row["object"], list)
