from __future__ import annotations

import json

from formulaboost.cli import main


def test_formulaboost_cli_help():
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0


def test_formulaboost_demo_pipeline_writes_run_artifacts(tmp_path):
    out = tmp_path / "fb"
    code = main(["demo", "--out", str(out), "--run-id", "pytest_demo", "--count", "12", "--seed", "1"])
    assert code == 0

    run_dir = out / "runs" / "pytest_demo"
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "families.jsonl").is_file()
    assert (run_dir / "results.md").is_file()
    assert (run_dir / "metrics.csv").is_file()
    assert (run_dir / "objects.jsonl").is_file()
    assert (run_dir / "top_family.json").is_file()

    first_family = json.loads((run_dir / "families.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first_family["domain"] == "modular_sidon"
    assert first_family["evaluation"]["invalid_rate"] == 0.0
    assert first_family["evaluation"]["pareto_rank"] >= 1
    assert "greedy_complete" in first_family["program"]["type"] or "greedy_complete" in first_family["pretty"]


def test_formulaboost_c4_demo_and_seed_export(tmp_path):
    out = tmp_path / "fb_c4"
    code = main(
        [
            "demo",
            "--domain",
            "c4_free_circulant",
            "--out",
            str(out),
            "--run-id",
            "pytest_c4",
            "--count",
            "8",
            "--seed",
            "2",
        ]
    )
    assert code == 0

    run_dir = out / "runs" / "pytest_c4"
    seeds = tmp_path / "seeds.jsonl"
    export_code = main(
        [
            "export-seeds",
            "--families",
            str(run_dir / "families.jsonl"),
            "--domain",
            "c4_free_circulant",
            "--params",
            '{"n":43}',
            "--top-k",
            "2",
            "--out",
            str(seeds),
        ]
    )
    assert export_code == 0
    lines = seeds.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["domain"] == "c4_free_circulant"


def test_formulaboost_synthetic_recovery(tmp_path):
    out = tmp_path / "synthetic"
    code = main(["synthetic-recovery", "--out", str(out), "--threshold", "1.01"])
    assert code == 0
    payload = json.loads((out / "synthetic_recovery.json").read_text(encoding="utf-8"))
    assert payload["recovered"] >= 2
    assert (out / "synthetic_recovery.md").is_file()
