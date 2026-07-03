#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="${OUT:-runs/main_81_matrix.jsonl}"
BUDGET_SECONDS="${BUDGET_SECONDS:-14400}"
STAGE="${STAGE:-main}"

mkdir -p "$(dirname "$OUT")"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m multilevel.cli matrix \
  --stage "$STAGE" \
  --budget-seconds "$BUDGET_SECONDS" \
  --problem misr \
  --problem unit_square \
  --problem guillotine \
  --out "$OUT"

ROWS="$(wc -l < "$OUT" | tr -d ' ')"
echo "wrote $OUT ($ROWS rows)"
