#!/bin/bash
#SBATCH --job-name=pb_explore
#SBATCH --output=runs/explore_hpc/slurm/%A_%a.out
#SBATCH --error=runs/explore_hpc/slurm/%A_%a.err
#SBATCH --array=0-0
#SBATCH --time=06:00:00
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/patternboost/multi-level}"
RESULTS_DIR="${RESULTS_DIR:-runs/explore_hpc}"
MATRIX="${MATRIX:-$PROJECT_DIR/runs/explore_matrix.jsonl}"
VENV="${VENV:-}"

cd "$PROJECT_DIR"
mkdir -p "$RESULTS_DIR/slurm"

if [ -n "$VENV" ] && [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
fi

export PYTHONPATH=src
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export VECLIB_MAXIMUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"

eval "$(
python3 - <<'PY' "$MATRIX" "${SLURM_ARRAY_TASK_ID}"
import json
import shlex
import sys

matrix, raw_index = sys.argv[1], int(sys.argv[2])
with open(matrix, encoding="utf-8") as handle:
    for index, line in enumerate(handle):
        if index == raw_index:
            row = json.loads(line)
            break
    else:
        raise SystemExit(f"matrix index out of range: {raw_index}")

def emit(name, value):
    if value is None:
        value = ""
    print(f"{name}={shlex.quote(str(value))}")

for key in (
    "problem",
    "rng_seed",
    "iterations",
    "population",
    "elite",
    "n",
    "grid",
    "run_id",
    "budget_seconds",
    "mixed_grid",
    "timeout_seconds",
    "threshold",
    "k",
):
    emit(key.upper(), row.get(key))
PY
)"

OUT_DIR="$RESULTS_DIR/$PROBLEM"

ARGS=(
  explore "$PROBLEM"
  --seed "$RNG_SEED"
  --iterations "$ITERATIONS"
  --population "$POPULATION"
  --elite "$ELITE"
  --n "$N"
  --grid "$GRID"
  --out "$OUT_DIR"
)

if [ -n "$RUN_ID" ]; then ARGS+=(--run-id "$RUN_ID"); fi
if [ -n "$BUDGET_SECONDS" ]; then ARGS+=(--budget-seconds "$BUDGET_SECONDS"); fi
if [ -n "$MIXED_GRID" ]; then ARGS+=(--mixed-grid "$MIXED_GRID"); fi
if [ -n "$TIMEOUT_SECONDS" ]; then ARGS+=(--timeout-seconds "$TIMEOUT_SECONDS"); fi
if [ -n "$THRESHOLD" ]; then ARGS+=(--threshold "$THRESHOLD"); fi
if [ -n "$K" ]; then ARGS+=(--k "$K"); fi

python3 -m multilevel.cli "${ARGS[@]}"
