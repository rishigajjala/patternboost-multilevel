#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MATRIX="${1:-runs/pilot_matrix.jsonl}"
OUT_ROOT="${2:-runs/full_matrix_baseline}"
ITERATIONS="${ITERATIONS:-100}"
N="${N:-12}"
GRID="${GRID:-8}"

ROWS="$(wc -l < "$MATRIX" | tr -d ' ')"
export PYTHONPATH=src

for ((INDEX=0; INDEX<ROWS; INDEX++)); do
  python3 -m multilevel.cli run-cell \
    --matrix "$MATRIX" \
    --index "$INDEX" \
    --out-root "$OUT_ROOT" \
    --iterations "$ITERATIONS" \
    --n "$N" \
    --grid "$GRID"
done

python3 -m multilevel.cli summary --root "$OUT_ROOT" --out "$OUT_ROOT/summary.csv"
