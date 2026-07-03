# Handoff Guide

This is the minimal workflow for a new student taking over the project.

## 1. Install and Test

```bash
cd multi-level
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e . -r requirements.txt
python3 -m pip install -r requirements-torch.txt
pytest -q
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/smoke
```

If this prints Python 3.9 or older, install Python 3.10+ first and recreate the
venv.

For a lightweight install, omit `requirements-torch.txt`; the base tests still
pass, and the transformer-specific test is skipped.

If `pytest` is missing:

```bash
python3 -m pip install pytest
```

## 2. Understand the Three Problems

Read these files in order:

1. `docs/EXPERIMENT_MATRIX.md`
2. `docs/PATTERNBOOST_EXPERIMENT_REPORT.md`
3. `docs/RESULTS.md`
4. `docs/HPC_JUBAIL.md`
5. `docs/archive/STRATEGY_STUDY_2026-06-30.md`

The active problem scope is `misr`, `unit_square`, and `guillotine`. Do not
count `epsilon_net`, `graph_separation`, or discarded square-stabbing-14-9
evidence in current paper tables.

## 3. Run a Tiny Local Cell

```bash
scripts/make_main_matrix.sh
PYTHONPATH=src python3 -m multilevel.cli patternboost-cell \
  --matrix runs/main_81_matrix.jsonl \
  --index 0 \
  --out-root runs/local_test \
  --iterations 20 \
  --population 16 \
  --elite 4 \
  --exact-every 5 \
  --train-every 5 \
  --model-samples 4 \
  --model-kind ngram \
  --checkpoint-every 1 \
  --n 8 \
  --grid 8
```

Check the output:

```bash
find runs/local_test -name summary.json -print
PYTHONPATH=src python3 -m multilevel.cli audit --root runs/local_test --out runs/local_test/audit/audit.json --csv runs/local_test/audit/audit.csv
```

## 4. Run on HPC

Use `docs/HPC_JUBAIL.md`. Always run a small smoke/slice before a full array.

Recommended first HPC sequence:

```bash
scripts/sync_to_hpc.sh
ssh sg9396@jubail.abudhabi.nyu.edu
cd ~/patternboost/multi-level
scripts/prepare_hpc_scratch_venv.sh
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/hpc_smoke
scripts/make_main_matrix.sh
```

## 5. Reporting Rule

Only report a candidate when all three are true:

1. It appears in `summary.json`.
2. Its `best_certificate_path` exists.
3. `multilevel verify` or `multilevel audit` recomputes the same value.

For wall-time-killed jobs, use checkpoint values only as live progress, not as
final paper-table rows.

## 6. Common Gotchas

- `--time` in Slurm is a wall limit. A row can finish earlier if it reaches
  `--iterations`.
- `budget_seconds` is the internal stop condition checked by the Python runner.
- `--resume` only works if the same output cell directory already contains
  `checkpoint.json`.
- `runs/` is ignored by git. Copy final certificates or summaries into a
  documented artifact directory only when they are meant to be preserved.
