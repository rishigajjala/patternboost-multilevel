#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MATRIX="${1:-runs/pilot_matrix.jsonl}"
OUT_ROOT="${2:-runs/full_matrix_patternboost}"
ITERATIONS="${ITERATIONS:-100}"
N="${N:-12}"
GRID="${GRID:-8}"
POPULATION="${POPULATION:-32}"
ELITE="${ELITE:-6}"
EXACT_EVERY="${EXACT_EVERY:-5}"
TRAIN_EVERY="${TRAIN_EVERY:-10}"
MODEL_SAMPLES="${MODEL_SAMPLES:-16}"
MODEL_KIND="${MODEL_KIND:-auto}"
MODEL_EPOCHS="${MODEL_EPOCHS:-3}"
BLOCK_SIZE="${BLOCK_SIZE:-128}"
CHECKPOINT_EVERY="${CHECKPOINT_EVERY:-1}"
RESUME="${RESUME:-}"

ROWS="$(wc -l < "$MATRIX" | tr -d ' ')"
export PYTHONPATH=src

for ((INDEX=0; INDEX<ROWS; INDEX++)); do
  python3 -m multilevel.cli patternboost-cell \
    --matrix "$MATRIX" \
    --index "$INDEX" \
    --out-root "$OUT_ROOT" \
    --iterations "$ITERATIONS" \
    --population "$POPULATION" \
    --elite "$ELITE" \
    --exact-every "$EXACT_EVERY" \
    --train-every "$TRAIN_EVERY" \
    --model-samples "$MODEL_SAMPLES" \
    --model-kind "$MODEL_KIND" \
    --model-epochs "$MODEL_EPOCHS" \
    --block-size "$BLOCK_SIZE" \
    --checkpoint-every "$CHECKPOINT_EVERY" \
    ${RESUME:+--resume} \
    --n "$N" \
    --grid "$GRID"
done

python3 -m multilevel.cli summary --root "$OUT_ROOT" --out "$OUT_ROOT/summary.csv"
