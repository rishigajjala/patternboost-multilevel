#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-runs/pilot_hpc}"
MATRIX="${MATRIX:-$PROJECT_DIR/runs/pilot_matrix.jsonl}"
SLURM_SCRIPT="${SLURM_SCRIPT:-$PROJECT_DIR/scripts/pilot_array.slurm}"
ARRAY_RANGE="${1:-${ARRAY_RANGE:-}}"

if [ ! -f "$MATRIX" ]; then
  echo "matrix not found: $MATRIX" >&2
  exit 1
fi
if [ ! -f "$SLURM_SCRIPT" ]; then
  echo "Slurm script not found: $SLURM_SCRIPT" >&2
  exit 1
fi

case "$RESULTS_DIR" in
  /*) RESULTS_PATH="$RESULTS_DIR" ;;
  *) RESULTS_PATH="$PROJECT_DIR/$RESULTS_DIR" ;;
esac
mkdir -p "$RESULTS_PATH/slurm"

export PROJECT_DIR RESULTS_DIR MATRIX

SBATCH_ARGS=()
if [ -n "$ARRAY_RANGE" ]; then
  SBATCH_ARGS+=(--array="$ARRAY_RANGE")
fi

echo "submitting pilot array"
echo "  project: $PROJECT_DIR"
echo "  matrix:  $MATRIX"
echo "  results: $RESULTS_DIR"
if [ -n "$ARRAY_RANGE" ]; then
  echo "  array:   $ARRAY_RANGE"
fi
cd "$PROJECT_DIR"
sbatch "${SBATCH_ARGS[@]}" "$SLURM_SCRIPT"
