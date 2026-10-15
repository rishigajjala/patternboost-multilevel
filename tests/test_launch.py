from __future__ import annotations

import json
import os
import subprocess

import pytest

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
        conda_env="/share/apps/NYUAD5/miniconda/3-4.11.0/envs/pytorch-2.7.1",
        pythonpath_extra="/home/sg9396/patternboost/multi-level/.venv-hpc/lib/python3.11/site-packages",
    )

    script = script_path.read_text(encoding="utf-8")
    assert "cd /home/sg9396/patternboost/multi-level" in script
    assert "--matrix runs/matrix.jsonl" in script
    assert "--out-root /home/sg9396/patternboost/multi-level/runs/hpc" in script
    assert "/System/Volumes/Data/home" not in script
    assert script.index("set +u") < script.index("conda activate") < script.index("set -u", script.index("set +u"))
    assert "module purge >/dev/null 2>&1 || true" in script
    assert "module load miniconda >/dev/null 2>&1 || true" in script
    assert (
        "export PYTHONPATH=src:/home/sg9396/patternboost/multi-level/.venv-hpc/lib/python3.11/site-packages"
        in script
    )
    assert "--model-embed-dim ${MODEL_EMBED_DIM:-96}" in script
    assert "--model-num-layers ${MODEL_NUM_LAYERS:-2}" in script


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


@pytest.mark.parametrize(
    ("row_iterations", "environment_iterations", "expected_iterations"),
    [
        (None, None, 1_000_000),
        (None, "17", 17),
        (1_000_000, "17", 1_000_000),
        (13, None, 13),
    ],
)
def test_patternboost_slurm_effective_iterations(
    tmp_path, monkeypatch, row_iterations, environment_iterations, expected_iterations
):
    from multilevel import cli

    row = {
        "problem": "misr",
        "representation": "triangle_free_rect",
        "local_search": "sequence_pair_pivot",
        "surrogate": "exact_lp_gap_pressure",
        "rng_seed": 1,
        "run_id": "iteration_cap_test",
        "stage": "main",
        "budget_seconds": 86400,
    }
    if row_iterations is not None:
        row["iterations"] = row_iterations
    matrix = tmp_path / "matrix.jsonl"
    matrix.write_text(json.dumps(row) + "\n", encoding="utf-8")
    script = write_slurm_array(
        matrix_path=matrix,
        out_path=tmp_path / "array.slurm",
        project_dir=tmp_path,
        results_dir=tmp_path / "results",
        time_limit="25:00:00",
        partition="compute",
        cpus_per_task=4,
        mem="16G",
    )

    # Execute the generated shell and capture its actual expanded CLI arguments.
    # The fake environment prevents any search or cluster setup from running.
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "activate").write_text(
        'python3() { printf "%s\\0" "$@" > "$CAPTURE_ARGS"; }\n', encoding="utf-8"
    )
    captured = tmp_path / "arguments"
    env = {
        "PATH": os.defpath,
        "VENV": str(venv),
        "CAPTURE_ARGS": str(captured),
        "SLURM_ARRAY_TASK_ID": "0",
    }
    if environment_iterations is not None:
        env["ITERATIONS"] = environment_iterations
    subprocess.run(["/bin/bash", str(script)], env=env, check=True, capture_output=True, text=True)
    argv = captured.read_bytes().decode().split("\0")[:-1]
    assert argv[:2] == ["-m", "multilevel.cli"]

    calls = []

    def capture_search(**kwargs):
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(cli, "run_patternboost", capture_search)
    args = cli.build_parser().parse_args(argv[2:])
    assert args.func(args) == 0
    assert len(calls) == 1
    assert calls[0]["iterations"] == expected_iterations
    assert calls[0]["budget_seconds"] == 86400
