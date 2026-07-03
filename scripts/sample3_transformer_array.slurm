#!/bin/bash
#SBATCH --job-name=pb_sample3
#SBATCH --output=runs/sample3_hpc/slurm/%A_%a.out
#SBATCH --error=runs/sample3_hpc/slurm/%A_%a.err
#SBATCH --array=0-2
#SBATCH --time=00:05:00
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/patternboost/multi-level}"
RESULTS_DIR="${RESULTS_DIR:-runs/sample3_hpc}"
MATRIX="${MATRIX:-$PROJECT_DIR/runs/sample3_matrix.jsonl}"
VENV="${VENV:-/scratch/$USER/pb_multilevel_venv}"

cd "$PROJECT_DIR"
mkdir -p "$RESULTS_DIR/slurm"
source "$VENV/bin/activate"
export PYTHONPATH=src
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export VECLIB_MAXIMUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

python3 -m multilevel.cli patternboost-cell \
  --matrix "$MATRIX" \
  --index "${SLURM_ARRAY_TASK_ID}" \
  --out-root "$RESULTS_DIR" \
  --iterations 2 \
  --population 8 \
  --elite 2 \
  --exact-every 1 \
  --train-every 1 \
  --model-samples 2 \
  --model-kind transformer \
  --model-epochs 2 \
  --block-size 128 \
  --checkpoint-every 1 \
  --n 6 \
  --grid 6
