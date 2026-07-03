#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SUMMARY="${1:-runs/summary.csv}"
OUT_DIR="${2:-runs/audit}"

export PYTHONPATH=src
python3 -m multilevel.cli audit \
  --summary "$SUMMARY" \
  --out "$OUT_DIR/audit.json" \
  --csv "$OUT_DIR/audit.csv"
