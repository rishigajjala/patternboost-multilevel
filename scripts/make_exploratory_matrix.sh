#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="${1:-runs/explore_overnight_matrix.jsonl}"
mkdir -p "$(dirname "$OUT")"

python3 - <<'PY' "$OUT"
import json
import sys

out = sys.argv[1]
rows = []

def add(**row):
    row.setdefault("iterations", 10_000)
    row.setdefault("population", 24)
    row.setdefault("elite", 6)
    row.setdefault("budget_seconds", 28_800)
    rows.append(row)

# Task A: rectangle graphs vs mixed square/segment representations.
# The mixed_grid parameter is the bounded verification grid. Larger values are
# stronger evidence but much slower, so these rows balance small witnesses with
# one harder grid-4 audit tier.
graph_rows = [
    dict(run_id="graph_g3_n5_dense", rng_seed=3101, n=5, grid=5, mixed_grid=3, timeout_seconds=4.0),
    dict(run_id="graph_g3_n6_balanced", rng_seed=3102, n=6, grid=6, mixed_grid=3, timeout_seconds=5.0),
    dict(run_id="graph_g3_n7_motif", rng_seed=3103, n=7, grid=7, mixed_grid=3, timeout_seconds=6.0),
    dict(run_id="graph_g4_n5_audit", rng_seed=4101, n=5, grid=6, mixed_grid=4, timeout_seconds=7.0),
    dict(run_id="graph_g4_n6_audit", rng_seed=4102, n=6, grid=7, mixed_grid=4, timeout_seconds=8.0),
    dict(run_id="graph_g4_n7_stress", rng_seed=4103, n=7, grid=8, mixed_grid=4, timeout_seconds=10.0),
]
for row in graph_rows:
    add(problem="graph_separation", **row)

# Task B: halfplane epsilon-net lower-bound rediscovery.
# These use exact k-subset enumeration. The later rows are aspirational; if they
# do not find exact witnesses, their missing nets are still useful diagnostics.
epsilon_rows = [
    dict(run_id="eps_n7_t3_k2", rng_seed=5201, n=7, grid=7, threshold=3, k=2),
    dict(run_id="eps_n8_t3_k2", rng_seed=5202, n=8, grid=8, threshold=3, k=2),
    dict(run_id="eps_n9_t4_k2", rng_seed=5203, n=9, grid=9, threshold=4, k=2),
    dict(run_id="eps_n10_t4_k3", rng_seed=5204, n=10, grid=10, threshold=4, k=3),
    dict(run_id="eps_n11_t4_k3", rng_seed=5205, n=11, grid=11, threshold=4, k=3),
    dict(run_id="eps_n12_t5_k3", rng_seed=5206, n=12, grid=12, threshold=5, k=3),
]
for row in epsilon_rows:
    add(problem="epsilon_net", **row)

with open(out, "w", encoding="utf-8") as handle:
    for row in rows:
        handle.write(json.dumps(row, sort_keys=True) + "\n")

print(f"wrote {len(rows)} rows to {out}")
PY
