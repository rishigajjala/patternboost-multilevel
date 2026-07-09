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

For final submission runs, deploy an exact git commit instead of the loose
working tree:

```bash
scripts/sync_git_commit_to_hpc.sh
```

This refuses tracked local changes, sends `git archive HEAD`, and creates a
clean commit-stamped directory such as
`/home/sg9396/patternboost/multi-level-<commit>`. Generate final matrices from
inside that deployed directory so each row records the same commit SHA that was
actually run.

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

## 3b. Generate the Exploratory Appendix Matrix

Use this only for the two exploratory tasks, `epsilon_net` and
`graph_separation`. Keep these results separate from the main
`misr`/`unit_square`/`guillotine` table.

```bash
scripts/make_exploratory_matrix.sh runs/explore_overnight_matrix.jsonl
wc -l runs/explore_overnight_matrix.jsonl
```

Expected row count: `12`.

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

For the exploratory appendix matrix, generate a separate Slurm script. Do not
reuse the main 81-row script.

```bash
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
```

The generated script invokes `multilevel.cli explore-cell`, reads each matrix
row directly, and writes one result directory per `problem/run_id`.

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

For exploratory runs, submit the generated exploratory script:

```bash
VENV=/scratch/$USER/pb_multilevel_venv sbatch scripts/explore_overnight_array.slurm
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

For final submission runs, also extract compact learning-curve data for plots:

```bash
PYTHONPATH=src python3 scripts/extract_learning_curves.py \
  runs/main_81_hpc \
  --out runs/main_81_hpc/report/learning_curves.csv
```

The final July 2026 submission snapshot was collected from a commit-stamped
deployment:

```text
/home/sg9396/patternboost/multi-level-8dd31ca1c888/runs/final_submission_20260708_131302
```

Its compact artifacts are committed under:

```text
docs/assets/final_submission_20260708_131302/
```

Use this committed artifact directory, not live checkpoint values, for
manuscript tables.

For exploratory runs, preserve only compact final artifacts in git:

```text
matrix.jsonl
*/summary.json
*/certificates/*.json
*/renderings/*.svg
final_audit.json
```

Do not commit full `events.jsonl` streams; they are useful for live monitoring
but too large for the repository.

## 9. Audited Exploratory Baseline

The most recent audited exploratory run is:

- Slurm job: `16501338`
- Run root: `runs/explore_overnight_20260704_051618`
- Status: `12/12 COMPLETED|0:0`
- Stderr: `0` nonempty files
- Best `epsilon_net`: `1.4545454545454546` from `eps_n11_t4_k3`
- Best `graph_separation`: exact `0.0`; best pressure/search
  `1.3845054945054946` from `graph_g3_n7_motif`
- Preserved snapshot:
  `docs/assets/exploratory_overnight_20260704_051618/`
