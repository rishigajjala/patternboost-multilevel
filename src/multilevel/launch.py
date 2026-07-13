from __future__ import annotations

import json
import os
import posixpath
import shlex
from pathlib import Path
from typing import Any


def read_matrix(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def matrix_row(path: str | Path, index: int) -> dict[str, Any]:
    rows = read_matrix(path)
    if index < 0 or index >= len(rows):
        raise IndexError(f"row index {index} outside matrix of length {len(rows)}")
    return rows[index]


def write_slurm_array(
    *,
    matrix_path: str | Path,
    out_path: str | Path,
    project_dir: str | Path,
    results_dir: str | Path,
    time_limit: str,
    partition: str,
    cpus_per_task: int,
    mem: str,
    runner: str = "patternboost",
    conda_env: str | None = None,
    pythonpath_extra: str | None = None,
) -> Path:
    rows = read_matrix(matrix_path)
    if not rows:
        raise ValueError("matrix has no rows")
    project = os.fspath(project_dir)
    matrix = os.fspath(matrix_path)
    results = os.fspath(results_dir)
    slurm_log_dir = posixpath.join(results, "slurm")
    if not posixpath.isabs(slurm_log_dir) or Path(project).exists():
        Path(slurm_log_dir).mkdir(parents=True, exist_ok=True)
    conda_line = (
        f'  conda activate "${{CONDA_ENV:-{conda_env}}}"'
        if conda_env
        else "  # conda environment not configured"
    )
    pythonpath = "src" if not pythonpath_extra else f"src:{pythonpath_extra}"
    if runner == "patternboost":
        command = "patternboost-cell"
        extra = (
            "--iterations ${ITERATIONS:-100} "
            "--population ${POPULATION:-32} "
            "--elite ${ELITE:-6} "
            "--exact-every ${EXACT_EVERY:-5} "
            "--train-every ${TRAIN_EVERY:-10} "
            "--model-samples ${MODEL_SAMPLES:-16} "
            "--model-kind ${MODEL_KIND:-auto} "
            "--model-epochs ${MODEL_EPOCHS:-3} "
            "--block-size ${BLOCK_SIZE:-128} "
            "--model-embed-dim ${MODEL_EMBED_DIM:-96} "
            "--model-num-heads ${MODEL_NUM_HEADS:-4} "
            "--model-num-layers ${MODEL_NUM_LAYERS:-2} "
            "--model-batch-size ${MODEL_BATCH_SIZE:-32} "
            "--model-learning-rate ${MODEL_LEARNING_RATE:-0.0003} "
            "--checkpoint-every ${CHECKPOINT_EVERY:-1} "
            "${RESUME:+--resume}"
        )
    elif runner == "search":
        command = "search-cell"
        extra = "--iterations ${ITERATIONS:-40} --population ${POPULATION:-24} --elite ${ELITE:-4} --exact-every ${EXACT_EVERY:-5}"
    elif runner == "explore":
        command = "explore-cell"
        extra = "--iterations ${ITERATIONS:-50} --population ${POPULATION:-32} --elite ${ELITE:-6}"
    elif runner == "baseline":
        command = "run-cell"
        extra = "--iterations ${ITERATIONS:-100}"
    else:
        raise ValueError(f"unknown runner: {runner}")
    script = f"""#!/bin/bash
#SBATCH --job-name=pb_multilevel
#SBATCH --output={slurm_log_dir}/%A_%a.out
#SBATCH --error={slurm_log_dir}/%A_%a.err
#SBATCH --array=0-{len(rows) - 1}
#SBATCH --time={time_limit}
#SBATCH --partition={partition}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={cpus_per_task}
#SBATCH --mem={mem}

set -euo pipefail
cd {shlex.quote(project)}
mkdir -p {shlex.quote(slurm_log_dir)}

VENV="${{VENV:-}}"
set +u
if [ -n "$VENV" ] && [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
else
  if command -v module >/dev/null 2>&1; then
    module purge >/dev/null 2>&1 || true
    module load miniconda >/dev/null 2>&1 || true
  fi
  if ! command -v conda >/dev/null 2>&1 && [ -f /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
  fi
  if command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base 2>/dev/null || true)"
    if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
      source "$CONDA_BASE/etc/profile.d/conda.sh"
    fi
{conda_line}
  fi
fi
set -u

export PYTHONPATH={shlex.quote(pythonpath)}
export OMP_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export OPENBLAS_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export MKL_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export NUMEXPR_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export VECLIB_MAXIMUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
python3 -m multilevel.cli {command} \\
  --matrix {shlex.quote(matrix)} \\
  --index "${{SLURM_ARRAY_TASK_ID}}" \\
  --out-root {shlex.quote(results)} \\
  {extra} \\
  --n "${{N:-12}}" \\
  --grid "${{GRID:-8}}"
"""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8")
    return target
