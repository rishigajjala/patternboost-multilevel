# FormulaBoost

FormulaBoost is a finite-to-family discovery prototype built alongside the
existing PatternBoost multi-level harness. It ingests finite examples, mines
compact DSL family programs, evaluates them on train/validation/test parameter
splits, and writes reproducible JSONL/Markdown artifacts.

## Implemented scope

- `modular_sidon` domain with exact verifier, scorer, affine canonicalization,
  greedy/random generation, and local repair.
- `c4_free_circulant` domain with exact C4 checker via common-neighbor counts,
  affine canonicalization, greedy/random generation, and local repair.
- Typed-enough executable DSL AST for modular set constructors:
  finite sets, residue classes, quadratic residues, units, unions,
  intersections, differences, translations, multiplications, and
  `greedy_complete`.
- Residue-frequency miner that proposes reusable family programs from finite
  examples for both current domains.
- Family evaluator with train/validation/test splits, normalized scores,
  invalid-output penalties, runtime accounting, novelty, and Pareto ranks.
- CLI commands for example generation, family search, single-family
  evaluation, seed export, synthetic DSL recovery, reports, and demos.

## Quick commands

Run the modular Sidon demo:

```bash
PYTHONPATH=src .venv/bin/python -m formulaboost.cli demo \
  --domain modular_sidon \
  --out runs/formulaboost_demo \
  --run-id demo_modular_sidon \
  --count 80 \
  --seed 0
```

Run the C4-free circulant demo:

```bash
PYTHONPATH=src .venv/bin/python -m formulaboost.cli demo \
  --domain c4_free_circulant \
  --out runs/formulaboost_c4_demo \
  --run-id demo_c4_free_circulant \
  --count 80 \
  --seed 0
```

Run the synthetic DSL recovery benchmark:

```bash
PYTHONPATH=src .venv/bin/python -m formulaboost.cli synthetic-recovery \
  --out runs/formulaboost_synthetic \
  --seed 0
```

Generate examples and search with an explicit config:

```bash
PYTHONPATH=src .venv/bin/python -m formulaboost.cli generate-examples \
  --domain modular_sidon \
  --params '{"n":31}' \
  --count 100 \
  --method greedy_local \
  --seed 0 \
  --out runs/formulaboost_manual/examples/sidon_n31.jsonl

PYTHONPATH=src .venv/bin/python -m formulaboost.cli search-families \
  --domain modular_sidon \
  --examples runs/formulaboost_manual/examples/sidon_n31.jsonl \
  --config configs/formulaboost_modular_sidon_mvp.json \
  --run-id sidon_manual \
  --out-root runs/formulaboost_manual/runs \
  --seed 0
```

Export generated seeds at a new size:

```bash
PYTHONPATH=src .venv/bin/python -m formulaboost.cli export-seeds \
  --families runs/formulaboost_demo/runs/demo_modular_sidon/families.jsonl \
  --domain modular_sidon \
  --params '{"n":101}' \
  --top-k 5 \
  --out runs/formulaboost_demo/sidon_n101_seeds.jsonl
```

## Output layout

Each `search-families` run writes:

```text
manifest.json
families.jsonl
objects.jsonl
metrics.csv
top_family.json
top_families.md
results.md
```

The current implementation is intentionally local and deterministic. It does
not require a private LLM API, GPU, or external experiment tracker.
