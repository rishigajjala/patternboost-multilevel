#!/bin/bash
#SBATCH --job-name=pb_multilevel
#SBATCH --output=runs/pilot_hpc/slurm/%A_%a.out
#SBATCH --error=runs/pilot_hpc/slurm/%A_%a.err
#SBATCH --array=0-161
#SBATCH --time=06:00:00
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/patternboost/multi-level}"
RESULTS_DIR="${RESULTS_DIR:-runs/pilot_hpc}"
MATRIX="${MATRIX:-$PROJECT_DIR/runs/pilot_matrix.jsonl}"
VENV="${VENV:-}"

cd "$PROJECT_DIR"
mkdir -p "$RESULTS_DIR/slurm"

if [ -n "$VENV" ] && [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
else
  if command -v module >/dev/null 2>&1; then
    module purge || true
    module load miniconda || true
  fi
  if ! command -v conda >/dev/null 2>&1 && [ -f /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
  fi
  if command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base 2>/dev/null || true)"
    if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
      source "$CONDA_BASE/etc/profile.d/conda.sh"
    fi
    conda activate "${CONDA_ENV:-patternboost}"
  fi
fi

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
  --iterations ${ITERATIONS:-100} --population ${POPULATION:-32} --elite ${ELITE:-6} --exact-every ${EXACT_EVERY:-5} --train-every ${TRAIN_EVERY:-10} --model-samples ${MODEL_SAMPLES:-16} --model-kind ${MODEL_KIND:-auto} --model-epochs ${MODEL_EPOCHS:-3} --block-size ${BLOCK_SIZE:-128} --checkpoint-every ${CHECKPOINT_EVERY:-1} ${RESUME:+--resume} \
  --n "${N:-12}" \
  --grid "${GRID:-8}"
