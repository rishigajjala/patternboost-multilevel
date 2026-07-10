#!/bin/bash
#SBATCH --job-name=pb_postprocess
#SBATCH --output=postprocess_%j.out
#SBATCH --error=postprocess_%j.err
#SBATCH --time=04:00:00
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

: "${PROJECT_DIR:?set PROJECT_DIR to the deployed PatternBoost directory}"
: "${RUN_ROOT:?set RUN_ROOT to the completed run root, relative to PROJECT_DIR or absolute}"
: "${COMPACTOR:?set COMPACTOR to compact_main_matrix_events.py}"

cd "$PROJECT_DIR"

case "$RUN_ROOT" in
  /*) RUN_PATH="$RUN_ROOT" ;;
  *) RUN_PATH="$PROJECT_DIR/$RUN_ROOT" ;;
esac

RESULTS_DIR="$RUN_PATH/main_results"
POSTPROCESS_DIR="$RUN_PATH/postprocess"
mkdir -p "$POSTPROCESS_DIR/audit" "$POSTPROCESS_DIR/analysis"

if [ -n "${VENV:-}" ] && [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
fi

export PYTHONPATH=src
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

python3 -m multilevel.cli summary \
  --root "$RESULTS_DIR" \
  --out "$POSTPROCESS_DIR/summary.csv"

python3 "$COMPACTOR" \
  "$RESULTS_DIR" \
  --out-dir "$POSTPROCESS_DIR/analysis" \
  --expected-rows 81 \
  --default-model-epochs 3 \
  --strict

python3 -m multilevel.cli audit \
  --summary "$POSTPROCESS_DIR/summary.csv" \
  --out "$POSTPROCESS_DIR/audit/audit.json" \
  --csv "$POSTPROCESS_DIR/audit/audit.csv"

printf 'postprocessing_complete %s\n' "$(date -Iseconds)"
