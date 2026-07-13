# Model-capacity experiment

## Question

Does substantially increasing transformer capacity and the available training
archive improve the best exact score under the same wall-clock budget?

This is a practical fixed-budget check. It cannot show that larger models never
help, and it does not justify the phrase "smallest possible transformer." A
defensible conclusion is: "we retained the compact architecture because the
tested scaled setting did not improve exact scores under the same budget."

## Selected configurations

The experiment uses the three highest-scoring standard automated configurations
for each of MISR, unit-square stabbing, and guillotine hardness in the final
81-cell table. The diversity-island unit-square follow-up is excluded because it
is a separate human-informed intervention. Exact-score ties are resolved by
configuration ID.

## Matched arms

Both arms use population 32, elite 6, exact scoring every 5 generations,
training every 10 generations, 16 model samples, 3 training epochs, context
length 128, no immigrants, no resolution-island retention, and the same
two-hour application budget. Geometry, local search, and surrogate are fixed
within each comparison.

| Arm | Initial pool | Training archive | Layers | Heads | Width |
|---|---:|---:|---:|---:|---:|
| compact | 32 | 48 | 2 | 4 | 96 |
| scaled | 256 | 256 | 4 | 8 | 192 |

The scaled transformer has roughly eight times the encoder parameters before
small vocabulary-dependent terms. Exact parameter counts, model-training time,
training-text counts, valid sample counts, generations, and exact calls are
recorded by every row.

Each row receives a freshly generated random state at matrix-generation time.
There is no repeated-seed axis and no warm-start certificate, target score, or
known construction in either arm.

## Generate and run

```bash
python3 -m multilevel.cli model-capacity-matrix \
  --budget-seconds 7200 \
  --out runs/model_capacity_2h/matrix.jsonl

python3 -m multilevel.cli make-slurm \
  --matrix runs/model_capacity_2h/matrix.jsonl \
  --out runs/model_capacity_2h/array.slurm \
  --project-dir "$HOME/patternboost/multi-level-COMMIT" \
  --results-dir "$HOME/patternboost/multi-level-COMMIT/runs/model_capacity_2h/results" \
  --time 02:30:00 \
  --partition compute \
  --cpus-per-task 4 \
  --mem 24G \
  --runner patternboost
```

After completion, collect and audit all certificates before interpreting scores:

```bash
python3 -m multilevel.cli summary \
  --root runs/model_capacity_2h/results \
  --out runs/model_capacity_2h/summary.csv

python3 -m multilevel.cli audit \
  --root runs/model_capacity_2h/results \
  --out runs/model_capacity_2h/audit.json \
  --csv runs/model_capacity_2h/audit.csv

python3 scripts/analyze_model_capacity.py \
  --matrix runs/model_capacity_2h/matrix.jsonl \
  --results-root runs/model_capacity_2h/results \
  --out-csv runs/model_capacity_2h/capacity_results.csv \
  --out-md runs/model_capacity_2h/capacity_results.md
```

## Reporting rule

Report exact verified scores and the number of comparisons in which scaling was
better, tied, or worse. Also report model-training time and completed
generations. Do not attribute a lower score solely to representational capacity
if the scaled arm completed materially fewer search generations.
