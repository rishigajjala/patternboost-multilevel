#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PILOT_ROOT="${PILOT_ROOT:-runs/pilot_hpc}"
SUMMARY="${SUMMARY:-$PILOT_ROOT/summary.csv}"
FOLLOWUP_MATRIX="${FOLLOWUP_MATRIX:-runs/followup_matrix.jsonl}"
SELECTION_OUT="${SELECTION_OUT:-runs/followup_selection.json}"
SLURM_OUT="${SLURM_OUT:-scripts/followup_array.slurm}"
RESULTS_DIR="${RESULTS_DIR:-runs/followup_hpc}"
TOP_K="${TOP_K:-3}"
BUDGET_SECONDS="${BUDGET_SECONDS:-43200}"
TIME_LIMIT="${TIME_LIMIT:-24:00:00}"
PARTITION="${PARTITION:-compute}"
CPUS_PER_TASK="${CPUS_PER_TASK:-4}"
MEM="${MEM:-16G}"
CONDA_ENV="${CONDA_ENV:-patternboost}"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

if [ ! -f "$SUMMARY" ]; then
  python3 -m multilevel.cli summary --root "$PILOT_ROOT" --out "$SUMMARY"
fi

python3 -m multilevel.cli followup-matrix \
  --summary "$SUMMARY" \
  --top-k "$TOP_K" \
  --budget-seconds "$BUDGET_SECONDS" \
  --selection-out "$SELECTION_OUT" \
  --out "$FOLLOWUP_MATRIX"

python3 -m multilevel.cli make-slurm \
  --matrix "$FOLLOWUP_MATRIX" \
  --out "$SLURM_OUT" \
  --project-dir "$PWD" \
  --results-dir "$RESULTS_DIR" \
  --time "$TIME_LIMIT" \
  --partition "$PARTITION" \
  --cpus-per-task "$CPUS_PER_TASK" \
  --mem "$MEM" \
  --runner patternboost \
  --conda-env "$CONDA_ENV"

echo "follow-up matrix: $FOLLOWUP_MATRIX"
echo "selection report: $SELECTION_OUT"
echo "Slurm script: $SLURM_OUT"
