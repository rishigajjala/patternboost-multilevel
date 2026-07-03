# PatternBoost Multi-Level Experiments

This repository contains the cleaned experiment harness for the PatternBoost
geometric extremal-search project. It focuses on three problems:

- `misr`: maximum independent set of rectangles LP-gap search
- `unit_square`: unit-square stabbing LP-gap search
- `guillotine`: rectangle packing / guillotine nonseparability search

The code generates random search instances, scores every reported candidate
with an exact problem-specific verifier, writes certificate JSON files, and
keeps checkpointable PatternBoost runs for local or NYUAD Jubail HPC execution.

## Repository Layout

```text
src/multilevel/          Python package and CLI
src/multilevel/scorers/  exact scorers and certificate verifiers
examples/               tiny explicit examples for smoke tests only
scripts/                local, HPC, collection, and monitoring helpers
tests/                  pytest regression tests
docs/                   handoff docs, current results, archived notes
runs/                   ignored local/HPC output directory
```

Generated artifacts are intentionally ignored by git. The old local run/output
folders from the working session were preserved in `.local_artifacts/` and are
not meant to be pushed.

## Setup

Use Python 3.10 or newer. Python 3.11 is recommended.

```bash
cd multi-level
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e . -r requirements.txt
```

If `python3 --version` is below 3.10, install a newer Python through conda,
Homebrew, or the NYUAD HPC module system before creating the virtual
environment.

Install PyTorch only if you want transformer-guided PatternBoost sampling:

```bash
python3 -m pip install -r requirements-torch.txt
```

Run the fast checks:

```bash
pytest -q
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/smoke
```

## First Local Run

Generate the current 81-row, no-seed main matrix:

```bash
scripts/make_main_matrix.sh
```

Run one PatternBoost cell locally:

```bash
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

Collect and audit results:

```bash
PYTHONPATH=src python3 -m multilevel.cli summary --root runs/local_test --out runs/local_test/summary.csv
PYTHONPATH=src python3 -m multilevel.cli audit --root runs/local_test --out runs/local_test/audit/audit.json --csv runs/local_test/audit/audit.csv
```

## NYUAD Jubail HPC

The short version is:

```bash
scripts/sync_to_hpc.sh
ssh sg9396@jubail.abudhabi.nyu.edu
cd ~/patternboost/multi-level
scripts/prepare_hpc_scratch_venv.sh
scripts/make_main_matrix.sh
PYTHONPATH=src python3 -m multilevel.cli make-slurm \
  --matrix runs/main_81_matrix.jsonl \
  --out scripts/main_81_array.slurm \
  --project-dir "$PWD" \
  --results-dir runs/main_81_hpc \
  --time 04:30:00 \
  --partition compute \
  --cpus-per-task 4 \
  --mem 16G \
  --runner patternboost
VENV=/scratch/$USER/pb_multilevel_venv sbatch scripts/main_81_array.slurm
```

Monitor the run:

```bash
scripts/monitor_hpc_run.sh JOB_ID runs/main_81_hpc
```

See [docs/HPC_JUBAIL.md](docs/HPC_JUBAIL.md) for the full step-by-step HPC
workflow, including smoke tests, resume commands, collection, and audit.

## Current Best Known Values

The most recent 4-hour previous-best warm-start run on Jubail produced:

```text
misr         1.4
unit_square 1.5000000000000004
guillotine  0.3
```

See [docs/PATTERNBOOST_EXPERIMENT_REPORT.md](docs/PATTERNBOOST_EXPERIMENT_REPORT.md)
for the detailed study report, including methodology, figures, observations,
and next steps. See [docs/RESULTS.md](docs/RESULTS.md) for the shorter job-ID
snapshot.

## Core Commands

Show available components:

```bash
PYTHONPATH=src python3 -m multilevel.cli registry
```

Score, verify, and render one bundled smoke example:

```bash
PYTHONPATH=src python3 -m multilevel.cli score misr examples/misr_small.json --out runs/misr_small.cert.json
PYTHONPATH=src python3 -m multilevel.cli verify runs/misr_small.cert.json
PYTHONPATH=src python3 -m multilevel.cli render runs/misr_small.cert.json --out runs/misr_small.svg
```

Resume a checkpointed cell:

```bash
PYTHONPATH=src python3 -m multilevel.cli patternboost-cell \
  --matrix runs/main_81_matrix.jsonl \
  --index 0 \
  --out-root runs/local_test \
  --iterations 200 \
  --resume
```

For a conceptual map of the 81 rows, see
[docs/EXPERIMENT_MATRIX.md](docs/EXPERIMENT_MATRIX.md). For day-to-day
handoff instructions, see [docs/HANDOFF.md](docs/HANDOFF.md).
