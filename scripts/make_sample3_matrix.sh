#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PILOT_MATRIX="${PILOT_MATRIX:-runs/pilot_matrix.jsonl}"
OUT="${OUT:-runs/sample3_matrix.jsonl}"
BUDGET_SECONDS="${BUDGET_SECONDS:-240}"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

if [ ! -f "$PILOT_MATRIX" ]; then
  python3 -m multilevel.cli matrix \
    --stage pilot \
    --budget-seconds 3600 \
    --out "$PILOT_MATRIX"
fi

python3 - "$PILOT_MATRIX" "$OUT" "$BUDGET_SECONDS" <<'PY'
import json
import sys
from pathlib import Path

pilot = Path(sys.argv[1])
out = Path(sys.argv[2])
budget = int(sys.argv[3])
rows = [json.loads(line) for line in pilot.read_text().splitlines() if line.strip()]
selected = [rows[index] for index in (0, 27, 54)]
for row in selected:
    row["stage"] = "sample3"
    row["budget_seconds"] = budget
    row["run_id"] = (
        row["run_id"]
        .replace("/budget3600/", f"/budget{budget}/")
        .replace("/pilot/", "/sample3/")
    )
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in selected))
for index, row in enumerate(selected):
    print(index, row["problem"], row["representation"], row["local_search"], row["surrogate"])
PY
