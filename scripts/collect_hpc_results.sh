#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$#" -eq 0 ]; then
  set -- runs/pilot_hpc runs/control_hpc runs/followup_hpc
fi

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"

for ROOT in "$@"; do
  SUMMARY="$ROOT/summary.csv"
  REPORT_DIR="$ROOT/report"
  AUDIT_DIR="$ROOT/audit"
  mkdir -p "$REPORT_DIR" "$AUDIT_DIR"
  echo "collecting $ROOT"
  python3 -m multilevel.cli summary --root "$ROOT" --out "$SUMMARY"
  python3 -m multilevel.cli report --summary "$SUMMARY" --out-dir "$REPORT_DIR"
  python3 -m multilevel.cli audit --summary "$SUMMARY" --out "$AUDIT_DIR/audit.json" --csv "$AUDIT_DIR/audit.csv"
done
