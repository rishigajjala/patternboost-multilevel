# PatternBoost Multi-Level Experiments

Code and exact certificates for *Towards Learning-Guided Discovery of Extremal
Geometric Constructions: A PatternBoost Study* (ALENEX 2027).

The final study contains 27 configurations for each of three problems:

| Problem | Objective | Recorded best | Original RNG seed |
| --- | --- | --- | --- |
| MISR | Rectangle independent-set clique-LP gap | 3/2 | `5381899176938748427` |
| Unit-square stabbing | Line-stabbing set-cover LP gap | 20/13 | `2072069136256961140` |
| Guillotine | Destroyed fraction under optimal recursive cuts | 1/3 | `4475353812576049258` |

All **81 recorded seeds, per-row runtime settings, and certificate hashes** are
committed in [the seed manifest](docs/assets/replacement_81_final_20260712/data/final_81_seeds.json).
The [complete runtime matrix](docs/assets/replacement_81_final_20260712/data/final_81_runtime.jsonl)
combines the historical matrix rows with their saved launch settings.
Generated searches go in the Git-ignored `runs/` directory; the committed
certificates and compact data are under `docs/assets/`.

## Install

Use Python 3.11 or 3.12 in a virtual environment:

```bash
git clone https://github.com/rishigajjala/patternboost-multilevel.git
cd patternboost-multilevel
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements.txt
```

The exact verifiers use NumPy, SciPy/HiGHS, and the bundled combinatorial
solvers. No commercial solver is required. Install PyTorch for guided searches:

```bash
python -m pip install -r requirements-torch.txt
```

Per-run dependency versions are recorded in the seed manifest and certificates.
The headline unit-square run used PyTorch **2.7.1**, while retained MISR and
guillotine runs record **2.8.0+cu128**. Use a separate matching environment when
comparing a historical run. The default optional requirements select 2.8.0.

## Verify the reported constructions

These commands work without PyTorch:

```bash
python reproduce.py --mode verify
python reproduce.py --mode smoke
```

Verification recomputes the scores of all 81 stored certificates. The smoke
mode checks the small-example scoring pipeline. Neither is a repeated-seed
search experiment.

## Re-run a paper configuration

Inspect a complete recorded configuration before launching it:

```bash
python reproduce.py --mode single --problem unit_square --dry-run
```

A normal single run uses that configuration's recorded seed and historical
**24-hour budget / 1,000,000-generation cap**:

```bash
python reproduce.py --mode single --problem unit_square
```

Use `--problem misr` or `--problem guillotine` for their headline cells.
`--paper-seeds` is accepted explicitly; `--seed INTEGER` selects a different
single-run seed, and `--fresh-seeds` generates and records new seeds.
Every invocation writes its effective matrix in an isolated run directory.
For a deliberately shorter comparison, both overrides change the matrix row:

```bash
python reproduce.py --mode single --problem misr --iterations 200 --budget-seconds 3600
```

Short runs and changed seeds may not reach a paper record. Generation counts
are not interchangeable across different populations or training schedules.
Fixed seeds also do not guarantee bitwise agreement across library versions,
hardware, or source revisions. Historical source revisions are recorded per
row; this entry point runs the checked-out harness with the recorded settings.

## The three historical cohorts

| Cohort | Rows | Initial n / grid | Population / elite | Initial pool / immigrants per generation | Train interval |
| --- | ---: | --- | --- | --- | ---: |
| Retained July 9 | 36 (12 per problem) | 8 / 8 | 32 / 6 | 32 / 0 | 7 |
| Main July 11 replacements | 42 | MISR/guillotine: 12 / 8; unit-square: 20 / 16 | 16 / 4 | 16 / 0 | 10 |
| Unit-square follow-up | 3 | 20 / 16 | 32 / 12 | 128 / 4, resolution diversity enabled | 10 |

Both headline MISR and guillotine records belong to the retained cohort.
Assigning one setting tuple per problem loses this distinction. The ordinary
`multilevel.cli matrix --stage main` command generates the older design and
fresh seeds; use the committed final runtime matrix for the paper's final grid.

## Full matrix and HPC

Preview or run the same 81 per-row configurations locally:

```bash
python reproduce.py --mode full --parallel 4 --dry-run
python reproduce.py --mode full --parallel 4
```

For Slurm, check out the project and keep the results on the cluster's scratch
filesystem. With the project environment activated, generate a 25-hour array:

```bash
python -m multilevel.cli make-slurm \
  --matrix docs/assets/replacement_81_final_20260712/data/final_81_runtime.jsonl \
  --out runs/paper_81_array.slurm \
  --project-dir "$PWD" \
  --results-dir "$SCRATCH/patternboost-results" \
  --time 25:00:00 --partition compute --cpus-per-task 4 --mem 16G \
  --runner patternboost
```

The PatternBoost Slurm fallback cap is 1,000,000 generations. Explicit matrix
fields take precedence over launcher defaults. To submit shorter jobs, create
rows with explicitly reduced iteration and wall-clock budgets instead of
assuming a CLI fallback overrides the paper matrix.

Read [ARTIFACT_EVALUATION.md](ARTIFACT_EVALUATION.md) for evaluation modes,
source provenance, analysis regeneration, output locations, and limitations.
[docs/HPC_JUBAIL.md](docs/HPC_JUBAIL.md) documents cluster-specific setup.
Sync helpers require an explicit account, for example
`REMOTE=NETID@jubail.abudhabi.nyu.edu scripts/sync_to_hpc.sh`.

## Data, reports, and development

- [Final 81-cell evidence](docs/assets/replacement_81_final_20260712)
- [Full report PDF](docs/manuscript/patternboost_81_run_analysis.pdf) and
  [analysis guide](docs/FINAL_81_ANALYSIS.md)
- [Recorded implementation details](docs/COLLABORATOR_EXPERIMENT_DETAILS.md)
- [Model-capacity study](docs/MODEL_CAPACITY_EXPERIMENT.md)
- [Exploratory appendix tasks](docs/EXPLORATORY_RESULTS.md)
- [Separate FormulaBoost prototype](docs/FORMULABOOST.md)

For regression checks:

```bash
python -m pip install pytest
python -m pytest -q
```

This public Git repository is versioned but its default branch can change.
An immutable publication requires a separately deposited, versioned archive;
no DOI is claimed here.
