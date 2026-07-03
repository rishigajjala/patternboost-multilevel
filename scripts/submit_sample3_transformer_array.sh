#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-runs/sample3_hpc}"
MATRIX="${MATRIX:-$PROJECT_DIR/runs/sample3_matrix.jsonl}"
SLURM_SCRIPT="${SLURM_SCRIPT:-$PROJECT_DIR/scripts/sample3_transformer_array.slurm}"
VENV="${VENV:-/scratch/$USER/pb_multilevel_venv}"
ARRAY_RANGE="${1:-${ARRAY_RANGE:-}}"

cd "$PROJECT_DIR"
if [ ! -f "$MATRIX" ]; then
  OUT="$MATRIX" scripts/make_sample3_matrix.sh
fi
mkdir -p "$RESULTS_DIR/slurm"

export PROJECT_DIR RESULTS_DIR MATRIX VENV

SBATCH_ARGS=()
if [ -n "$ARRAY_RANGE" ]; then
  SBATCH_ARGS+=(--array="$ARRAY_RANGE")
fi

echo "submitting sample3 transformer array"
echo "  project: $PROJECT_DIR"
echo "  matrix:  $MATRIX"
echo "  results: $RESULTS_DIR"
echo "  venv:    $VENV"
if [ -n "$ARRAY_RANGE" ]; then
  echo "  array:   $ARRAY_RANGE"
fi
sbatch "${SBATCH_ARGS[@]}" "$SLURM_SCRIPT"
