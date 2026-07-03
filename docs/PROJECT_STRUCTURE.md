# Project Structure

## Python Package

```text
src/multilevel/cli.py              CLI entry point
src/multilevel/components.py       experiment component registry
src/multilevel/patternboost.py     checkpointable PatternBoost runner
src/multilevel/search.py           component-aware surrogate search runner
src/multilevel/local_only.py       exact-scored random baseline
src/multilevel/representations.py  representation generators and repairs
src/multilevel/mutations.py        local mutation operators
src/multilevel/modeling.py         n-gram and transformer model helpers
src/multilevel/scorers/            exact problem scorers
src/multilevel/report.py           CSV/SVG/Markdown report generation
src/multilevel/audit.py            certificate audit logic
```

## Data and Outputs

- `examples/` contains only tiny examples for explicit smoke tests.
- `runs/` is the default output directory and is ignored by git.
- `docs/assets/study_assets/` contains curated figures and certificate examples
  from prior study notes.
- `.local_artifacts/` contains local generated clutter preserved during cleanup;
  it is ignored by git.

## Scripts

- `scripts/make_main_matrix.sh`: write the 81-row three-problem matrix.
- `scripts/run_one_cell.sh`: run one matrix row locally.
- `scripts/prepare_hpc_scratch_venv.sh`: create the Jubail scratch venv.
- `scripts/sync_to_hpc.sh`: rsync source to Jubail.
- `scripts/monitor_hpc_run.sh`: inspect Slurm and result health.
- `scripts/collect_hpc_results.sh`: collect summary/report/audit outputs.

## Tests

Run all tests:

```bash
pytest -q
```

The tests cover exact scorers, representation repair/mutation, model helpers,
follow-up matrix selection, and nontrivial PatternBoost filters.

