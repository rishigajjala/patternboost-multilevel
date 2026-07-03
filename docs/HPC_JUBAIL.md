# NYUAD Jubail HPC Workflow

These commands assume the NYUAD username `sg9396` and the default remote
directory `~/patternboost/multi-level`. Override `REMOTE` or `REMOTE_DIR` if
needed.

## 1. Sync from Local Machine

From the local project root:

```bash
scripts/sync_to_hpc.sh
```

Dry run first:

```bash
DRY_RUN=1 scripts/sync_to_hpc.sh
```

The sync excludes `.git`, virtualenvs, local generated outputs, and `runs/`.

## 2. Create the HPC Python Environment

On Jubail:

```bash
ssh sg9396@jubail.abudhabi.nyu.edu
cd ~/patternboost/multi-level
scripts/prepare_hpc_scratch_venv.sh
source /scratch/$USER/pb_multilevel_venv/bin/activate
```

Run a smoke check:

```bash
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/hpc_smoke
pytest -q
```

## 3. Generate the Main Matrix

```bash
scripts/make_main_matrix.sh
wc -l runs/main_81_matrix.jsonl
```

Expected row count: `81`.

## 4. Generate a Slurm Array

```bash
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
```

The generated script reads these optional environment overrides:

```bash
export VENV=/scratch/$USER/pb_multilevel_venv
export ITERATIONS=400
export POPULATION=32
export ELITE=6
export EXACT_EVERY=5
export TRAIN_EVERY=7
export MODEL_SAMPLES=16
export MODEL_KIND=transformer
export MODEL_EPOCHS=3
export CHECKPOINT_EVERY=1
export N=8
export GRID=8
```

## 5. Submit a Smoke Slice

Run three representative rows first:

```bash
VENV=/scratch/$USER/pb_multilevel_venv \
ITERATIONS=20 \
POPULATION=16 \
MODEL_KIND=ngram \
sbatch --array=0,27,54 scripts/main_81_array.slurm
```

Monitor it:

```bash
scripts/monitor_hpc_run.sh JOB_ID runs/main_81_hpc
```

If the smoke slice finishes cleanly, submit the full array:

```bash
VENV=/scratch/$USER/pb_multilevel_venv \
ITERATIONS=400 \
TRAIN_EVERY=7 \
MODEL_KIND=transformer \
sbatch scripts/main_81_array.slurm
```

## 6. Monitor

```bash
squeue -u "$USER"
sacct -j JOB_ID --format=JobID,State,Elapsed,MaxRSS,ExitCode
scripts/monitor_hpc_run.sh JOB_ID runs/main_81_hpc
```

`scripts/monitor_hpc_run.sh` reports:

- Slurm state counts
- non-OK Slurm rows
- summary/checkpoint/event counts
- nonempty stderr count
- current best values from summaries or live checkpoints

## 7. Resume

A row can stop because Slurm wall time expires. If its output directory contains
`checkpoint.json`, rerun the same matrix/root with resume enabled:

```bash
VENV=/scratch/$USER/pb_multilevel_venv \
RESUME=1 \
ITERATIONS=1000 \
sbatch --array=ROW_INDEX scripts/main_81_array.slurm
```

Do not change `--out-root` when resuming in place. To preserve the old run,
copy checkpoint directories to a new run root first.

## 8. Collect and Audit

```bash
scripts/collect_hpc_results.sh runs/main_81_hpc
```

This writes:

```text
runs/main_81_hpc/summary.csv
runs/main_81_hpc/report/
runs/main_81_hpc/audit/audit.json
runs/main_81_hpc/audit/audit.csv
```

A result is paper-usable only when the audit passes.

