#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: scripts/monitor_hpc_run.sh JOB_ID RESULTS_ROOT [RESULTS_ROOT ...]" >&2
  exit 2
fi

JOB_ID="$1"
shift

cd "$(dirname "$0")/.."

export PATH=/opt/slurm/default/bin:/usr/local/bin:/usr/bin:/bin:$PATH
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "time: $(date +%Y-%m-%dT%H:%M:%S%z)"
echo
echo "slurm state for job $JOB_ID"
if command -v squeue >/dev/null 2>&1; then
  squeue -r -j "$JOB_ID" -h -o "%T %R" 2>/dev/null | sort | uniq -c || true
else
  echo "squeue not found"
fi

echo
echo "sacct counts"
if command -v sacct >/dev/null 2>&1; then
  sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed -P -n 2>/dev/null |
    awk -F'|' -v job="$JOB_ID" '$1 ~ "^"job"_[0-9]+$" {c[$2"|"$3]++} END {for (k in c) print c[k], k}' |
    sort || true
else
  echo "sacct not found"
fi

echo
echo "non-ok rows"
if command -v sacct >/dev/null 2>&1; then
  sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed,Reason -P -n 2>/dev/null |
    awk -F'|' -v job="$JOB_ID" '$1 ~ "^"job"_[0-9]+$" && ($2 !~ /^(RUNNING|COMPLETED)$/ || $3 != "0:0") {print}' |
    sed -n '1,80p' || true
fi

for ROOT in "$@"; do
  echo
  echo "result root: $ROOT"
  printf "summaries="; find "$ROOT" -name summary.json 2>/dev/null | wc -l | tr -d ' '
  echo
  printf "checkpoints="; find "$ROOT" -name checkpoint.json 2>/dev/null | wc -l | tr -d ' '
  echo
  printf "events="; find "$ROOT" -name events.jsonl 2>/dev/null | wc -l | tr -d ' '
  echo
  printf "nonempty_stderr="; find "$ROOT/slurm" -name '*.err' -size +0c 2>/dev/null | wc -l | tr -d ' '
  echo
done

echo
echo "best values"
"$PYTHON_BIN" - "$@" <<'PY'
import json
import math
import pathlib
import statistics
import sys

for raw_root in sys.argv[1:]:
    root = pathlib.Path(raw_root)
    chosen = {}
    for cp in root.rglob("checkpoint.json"):
        chosen[cp.parent] = cp
    for sp in root.rglob("summary.json"):
        chosen[sp.parent] = sp

    rows = []
    errors = 0
    for path in chosen.values():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            errors += 1
            continue
        problem = data.get("problem")
        score = data.get("best_exact_score")
        cert = None
        cert_path = data.get("best_certificate_path")
        if cert_path and pathlib.Path(cert_path).exists():
            try:
                cert = json.loads(pathlib.Path(cert_path).read_text(encoding="utf-8"))
            except Exception:
                cert = None
        if (not isinstance(score, (int, float)) or not math.isfinite(score)) and cert:
            score = cert.get("score")
        if problem not in {"misr", "unit_square", "guillotine"}:
            continue
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            continue

        size = tau = destroyed = None
        if cert:
            if problem == "misr":
                size = len(cert.get("rectangles") or [])
            elif problem == "unit_square":
                size = len(cert.get("squares") or [])
                tau = cert.get("tau_int")
            elif problem == "guillotine":
                size = cert.get("n") if isinstance(cert.get("n"), int) else len(cert.get("rectangles") or [])
                destroyed = cert.get("destroyed")
        rows.append(
            {
                "problem": problem,
                "score": float(score),
                "source": path.name,
                "iteration": data.get("completed_iterations") or data.get("next_generation"),
                "path": str(path.parent),
                "size": size,
                "tau": tau,
                "destroyed": destroyed,
            }
        )

    print(f"## {raw_root} rows={len(rows)} parse_errors={errors}")
    for problem in ("misr", "unit_square", "guillotine"):
        vals = [row for row in rows if row["problem"] == problem]
        if not vals:
            print(f"{problem}: none")
            continue
        vals.sort(key=lambda row: row["score"], reverse=True)
        best = vals[0]
        extras = []
        if best["size"] is not None:
            extras.append(f"size={best['size']}")
        if best["tau"] is not None:
            extras.append(f"tau={best['tau']}")
        if best["destroyed"] is not None:
            extras.append(f"destroyed={best['destroyed']}")
        scores = [row["score"] for row in vals]
        print(
            f"{problem}: best={best['score']} median={statistics.median(scores)} "
            f"count={len(vals)} iter={best['iteration']} source={best['source']} "
            f"{' '.join(extras)} path={best['path']}"
        )
PY
