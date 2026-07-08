# Exploratory Results Snapshot

Last audited run date: 2026-07-04, Asia/Dubai.

This page records the two exploratory tasks that are separate from the main
three-problem PatternBoost table. These rows are useful for direction and
appendix-style reporting, but they should not be mixed with the main
`misr`/`unit_square`/`guillotine` results.

## Final Audited Run

- Slurm job: `16501338`
- Remote run root: `runs/explore_overnight_20260704_051618`
- Preserved repository snapshot:
  `docs/assets/exploratory_overnight_20260704_051618/`
- Status: `12/12 COMPLETED|0:0`
- Summaries: `12/12`
- Nonempty stderr: `0`
- Bad JSON / stale streams / validation errors: `0`
- Matrix: `12` expected rows, `12` unique fresh seeds, no old fixed-seed hits
- Remote result size: `639M`

The repository snapshot preserves the matrix, per-row summaries, best
certificates, best SVG renderings, and a compact `final_audit.json`. The large
event streams remain only in the ignored remote/local `runs/` tree.

## Best Values

| Task | Best exact value | Row | Notes |
| --- | ---: | --- | --- |
| `epsilon_net` | `1.4545454545454546` | `eps_n11_t4_k3` | exact certificate verified; pressure/search best was also this row (`16.0`) |
| `graph_separation` | `0.0` | `graph_g3_n5_dense` | no bounded-grid separation witness certified in this run |

The best graph-separation pressure/search score was `1.3845054945054946` from
`graph_g3_n7_motif`, but its exact score remained `0.0`.

## Per-Row Summary

| Problem | Run ID | Exact | Iterations | Stop reason | Elapsed hours | Certificate |
| --- | --- | ---: | ---: | --- | ---: | --- |
| `epsilon_net` | `eps_n7_t3_k2` | `1.2857142857142856` | `10000` | `completed` | `0.46` | `b9548696bf7c` |
| `epsilon_net` | `eps_n8_t3_k2` | `1.125` | `10000` | `completed` | `0.55` | `5b76f22df128` |
| `epsilon_net` | `eps_n9_t4_k2` | `1.3333333333333333` | `10000` | `completed` | `0.72` | `b4a3b8c57c84` |
| `epsilon_net` | `eps_n10_t4_k3` | `0.0` | `10000` | `completed` | `2.85` | `42c97e5c37af` |
| `epsilon_net` | `eps_n11_t4_k3` | `1.4545454545454546` | `10000` | `completed` | `3.56` | `3366e1460227` |
| `epsilon_net` | `eps_n12_t5_k3` | `0.0` | `9781` | `budget_exhausted` | `8.00` | `d8b016d003c7` |
| `graph_separation` | `graph_g3_n5_dense` | `0.0` | `572` | `budget_exhausted` | `8.01` | `59462871b0af` |
| `graph_separation` | `graph_g3_n6_balanced` | `0.0` | `424` | `budget_exhausted` | `8.01` | `9e5339ddb649` |
| `graph_separation` | `graph_g3_n7_motif` | `0.0` | `329` | `budget_exhausted` | `8.01` | `a64f269680eb` |
| `graph_separation` | `graph_g4_n5_audit` | `0.0` | `319` | `budget_exhausted` | `8.01` | `08f6a59fafc5` |
| `graph_separation` | `graph_g4_n6_audit` | `0.0` | `259` | `budget_exhausted` | `8.03` | `1f3a42d0fe61` |
| `graph_separation` | `graph_g4_n7_stress` | `0.0` | `191` | `budget_exhausted` | `8.00` | `5b201b38653c` |

## Interpretation

The epsilon-net exploratory run found nontrivial exact witnesses at small
sizes, with the strongest row reaching `1.4545454545454546`. The harder
`n=12, t=5, k=3` row did not find a positive exact certificate within the
8-hour budget.

The graph-separation run did not certify a separation witness. The pressure
scores indicate the search found geometrically stressful rectangle graphs, but
the bounded mixed square/segment verifier did not produce exact obstruction
evidence. The next useful step is not more of the same generic search; it is
to add a stronger non-representability verifier or a smaller structured graph
family with clearer unsat cores.

## Reproduction

On Jubail, after preparing the venv:

```bash
scripts/make_exploratory_matrix.sh runs/explore_overnight_matrix.jsonl
PYTHONPATH=src python3 -m multilevel.cli make-slurm \
  --matrix runs/explore_overnight_matrix.jsonl \
  --out scripts/explore_overnight_array.slurm \
  --project-dir "$PWD" \
  --results-dir runs/explore_overnight_$(date +%Y%m%d_%H%M%S) \
  --time 09:00:00 \
  --partition compute \
  --cpus-per-task 1 \
  --mem 8G \
  --runner explore
VENV=/scratch/$USER/pb_multilevel_venv sbatch scripts/explore_overnight_array.slurm
```

Verify completed certificates from a result root:

```bash
find runs/explore_overnight_YYYYMMDD_HHMMSS -name summary.json -print
PYTHONPATH=src python3 -m multilevel.cli verify PATH_TO_BEST_CERTIFICATE.json
```
