from __future__ import annotations

import json

from multilevel.launch import write_slurm_array


def test_write_slurm_array_preserves_target_hpc_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    matrix = tmp_path / "runs" / "matrix.jsonl"
    matrix.parent.mkdir(parents=True)
    matrix.write_text(json.dumps({"schema": "run_matrix_row_v1"}) + "\n", encoding="utf-8")

    script_path = write_slurm_array(
        matrix_path="runs/matrix.jsonl",
        out_path=tmp_path / "array.slurm",
        project_dir="/home/sg9396/patternboost/multi-level",
        results_dir="/home/sg9396/patternboost/multi-level/runs/hpc",
        time_limit="00:05:00",
        partition="compute",
        cpus_per_task=1,
        mem="2G",
    )

    script = script_path.read_text(encoding="utf-8")
    assert "cd /home/sg9396/patternboost/multi-level" in script
    assert "--matrix runs/matrix.jsonl" in script
    assert "--out-root /home/sg9396/patternboost/multi-level/runs/hpc" in script
    assert "/System/Volumes/Data/home" not in script


def test_write_slurm_array_supports_exploratory_runner(tmp_path):
    matrix = tmp_path / "explore_matrix.jsonl"
    matrix.write_text(json.dumps({"problem": "epsilon_net", "rng_seed": 0}) + "\n", encoding="utf-8")

    script_path = write_slurm_array(
        matrix_path=matrix,
        out_path=tmp_path / "explore.slurm",
        project_dir="/home/sg9396/patternboost/multi-level",
        results_dir="/home/sg9396/patternboost/multi-level/runs/explore",
        time_limit="01:00:00",
        partition="compute",
        cpus_per_task=2,
        mem="8G",
        runner="explore",
    )

    script = script_path.read_text(encoding="utf-8")
    assert "python3 -m multilevel.cli explore-cell" in script
    assert "--out-root /home/sg9396/patternboost/multi-level/runs/explore" in script


def test_write_slurm_array_creates_log_dir_on_target_filesystem(tmp_path):
    matrix = tmp_path / "matrix.jsonl"
    matrix.write_text(json.dumps({"problem": "epsilon_net", "rng_seed": 0}) + "\n", encoding="utf-8")
    results = tmp_path / "runs" / "explore"

    write_slurm_array(
        matrix_path=matrix,
        out_path=tmp_path / "array.slurm",
        project_dir=tmp_path,
        results_dir=results,
        time_limit="00:05:00",
        partition="compute",
        cpus_per_task=1,
        mem="2G",
        runner="explore",
    )

    assert (results / "slurm").is_dir()
