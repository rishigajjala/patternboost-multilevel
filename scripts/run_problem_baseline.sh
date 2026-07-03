#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROBLEM="${1:?usage: run_problem_baseline.sh PROBLEM [OUT_ROOT]}"
OUT_ROOT="${2:-runs/problem_baseline}"
ITERATIONS="${ITERATIONS:-100}"
N="${N:-12}"
GRID="${GRID:-8}"

export PYTHONPATH=src
python3 - <<'PY' "$PROBLEM" "$OUT_ROOT" "$ITERATIONS" "$N" "$GRID"
import secrets
import subprocess
import sys

problem, out_root, iterations, n, grid = sys.argv[1:]
rng_seed = secrets.randbits(63)
out = f"{out_root}/{problem}"
cmd = [
    sys.executable, "-m", "multilevel.cli", "local-only", problem,
    "--seed", str(rng_seed),
    "--iterations", iterations,
    "--n", n,
    "--grid", grid,
    "--out", out,
]
print("+", " ".join(cmd), flush=True)
subprocess.check_call(cmd)
PY

python3 -m multilevel.cli summary --root "$OUT_ROOT" --out "$OUT_ROOT/summary.csv"
