# Artifact evaluation

This artifact provides exact verifiers, stored constructions, and a search
harness for the three-problem PatternBoost study. The final data contain one
historical run for each of 81 configurations; they do not constitute a
matched repeated-seed robustness study.

## Setup and dependencies

Follow the root [README](README.md). Python 3.11 is the recommended historical
major/minor version. Core dependencies are NumPy 2.0.2 and SciPy 1.13.1.
PyTorch is optional for certificate verification and smoke checks, and required
for transformer-guided reruns. Searches require an explicit n-gram choice to
deviate from the transformer setup; it is not silently substituted for a
missing transformer installation.

The [seed manifest](docs/assets/replacement_81_final_20260712/data/final_81_seeds.json)
records dependencies per certificate. In particular, the unit-square headline
used Python 3.11.14 / torch 2.7.1; retained MISR and guillotine certificates
record Python 3.11.3 / torch 2.8.0+cu128. A current rerun can differ from the
historical trajectory even with the same seed. No commercial solver is needed.

## Mode 1: exact certificate verification

```bash
python reproduce.py --mode verify
```

The mapping lists all 81 final certificates. Every listed file must be present;
a missing file is an error, not a successful skip. Each stored construction is
recomputed by its problem-specific exact oracle, independently of the search.
This verifies the geometric claims, not the probability of rediscovering them.

## Mode 2: pipeline smoke check

```bash
python reproduce.py --mode smoke
```

This scores and verifies the small bundled examples without requiring PyTorch.
The smoke subcommand does not receive a `--model-kind` argument. A smoke pass
checks installation and the scoring pipeline rather than paper-level search
performance.

## Mode 3: one headline search

```bash
python reproduce.py --mode single --problem misr --dry-run
python reproduce.py --mode single --problem unit_square --dry-run
python reproduce.py --mode single --problem guillotine --dry-run
```

Remove `--dry-run` to search. The driver selects the unique matching final
configuration and uses the stored seed and complete historical settings.
Default budget is 86,400 seconds with a 1,000,000-generation safety cap.
`--paper-seeds` explicitly requests the default recorded-seed behavior.

| Problem | Recorded seed | n / grid | Population / elite | Train interval |
| --- | --- | --- | --- | ---: |
| MISR | `5381899176938748427` | 8 / 8 | 32 / 6 | 7 |
| Guillotine | `4475353812576049258` | 8 / 8 | 32 / 6 | 7 |
| Unit-square | `2072069136256961140` | 20 / 16 | 32 / 12 | 10 |

The unit-square row additionally uses an initial pool of 128, four immigrants
per generation, and resolution diversity. All three use exact scoring every
five generations, 16 requested model samples, three training epochs, and a
context length of 128.

Explicit changes are written into the effective matrix:

```bash
python reproduce.py --mode single --problem misr --seed 42 \
  --iterations 200 --budget-seconds 3600
```

Use a common configuration, code, environment, and budget when comparing
seeds. Report every seed, endpoint score, and time-to-target. The archived data
alone do not establish robustness across seeds, and a shorter run is not an
unsuccessful reproduction of the full 24-hour experiment.

## Mode 4: figures and tables

```bash
python -m pip install -r requirements-analysis.txt
python reproduce.py --mode figures
```

This regenerates analysis assets from the committed compact CSVs. It does not
repeat searches or require PyTorch. The separate model-capacity analysis uses
`scripts/analyze_model_capacity.py`; absent optional reference-score metadata
is reported as blank rather than raising a KeyError.

## Mode 5: full final grid

```bash
python reproduce.py --mode full --parallel 4 --dry-run
python reproduce.py --mode full --parallel 4
```

The final rows combine 36 retained July 9 runs, 42 main replacement runs, and
three unit-square follow-ups. The exact membership and settings are committed
in [final_81_runtime.jsonl](docs/assets/replacement_81_final_20260712/data/final_81_runtime.jsonl).
Single, full, and HPC paths all use these complete rows. Parallel worker
failures cause the driver to fail rather than reporting success.

`--mode matrix` materializes the final rows without launching a search.
The root README's Slurm command points directly to the same committed rows.
For full-budget arrays, request scheduler time longer than 24 hours so startup
and the final generation can complete. Historical checkpoint frequency was one
generation; a checkpoint-frequency change is a runtime deviation and can alter
throughput within a wall-clock budget.

## Seeds, outputs, and provenance

Seeds are 63-bit integers. Their decimal-string representation in the JSON
manifest prevents rounding through floating-point spreadsheet conversions.
The JSONL runtime rows preserve exact integer literals. The search saves
`rng_seed` in summary/checkpoint files; the effective input matrix is also
written for every invocation. Separate invocation directories prevent different
seed trials from overwriting one another.

Historical source commits are:

- retained 36: `20750a588a5b5d8e744689b9efa7538b5eaab26b`;
- replacement 42: `6f80dfec1a16c0d8428b97d587cb65f3e41354af`;
- follow-up 3: `87326f25dbec40525ec0895605e0608f51d1a7f4`.

Those revisions remain in repository history. The reproduction driver uses the
checked-out harness; the revision in each row is historical provenance, not an
automatic checkout or a claim that an old checkpoint can be resumed in new code.
The [runtime provenance note](docs/assets/replacement_81_final_20260712/data/final_81_runtime_provenance.json)
describes how the original matrix rows and saved summaries were joined.
The large raw event streams, checkpoints, and trained models are not committed.

An immutable archive must include the same reproduction entry point, complete
matrix and seeds, verifiers, all certificates, and installation instructions.
The public GitHub repository alone does not supply an immutable DOI deposit.
