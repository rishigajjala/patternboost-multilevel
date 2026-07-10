#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="${OUT:-runs/replacement_delta_matrix.jsonl}"
BUDGET_SECONDS="${BUDGET_SECONDS:-86400}"
STAGE="${STAGE:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$(dirname "$OUT")"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

"$PYTHON_BIN" -m multilevel.cli replacement-delta-matrix \
  --stage "$STAGE" \
  --budget-seconds "$BUDGET_SECONDS" \
  --problem misr \
  --problem unit_square \
  --problem guillotine \
  --out "$OUT"

ROWS="$(wc -l < "$OUT" | tr -d ' ')"
echo "wrote $OUT ($ROWS rows; expected 45)"
