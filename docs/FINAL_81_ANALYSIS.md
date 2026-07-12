# Updated final 81-cell experiment analysis

This page maps the publication-oriented analysis of the final PatternBoost
matrix for MISR, unit-square stabbing, and guillotine hardness.

## Primary report

- TeX: `docs/manuscript/patternboost_81_run_analysis.tex`
- PDF: `docs/manuscript/patternboost_81_run_analysis.pdf`
- Evidence commits: `20750a588a5b`, `6f80dfec1a16`, and `87326f25dbec`
- Dataset: `docs/assets/replacement_81_final_20260712`
- Design: 27 configurations per problem, 81 configurations total, and no
  repeated-seed axis

The report covers the complete endpoint table, every strict-record trajectory,
component marginals, behavior by cumulative transformer-training epoch and
search generation, exact construction renderings, limitations, and the full
81-row appendix.

## Principal CSV files

- `data/final_81_runs.csv`: one row per final configuration, including the
  three component choices, best exact score, certificate metadata, time to
  best, model epoch, throughput, and diagnostics.
- `data/final_81_epoch_history.csv`: all strict improvements plus one explicit
  endpoint per configuration. This is the source for score-versus-epoch,
  score-versus-generation, and score-versus-time plots.

The CSVs contain 81 endpoint rows and 529 history rows. Their best values are
`3/2` for MISR, `20/13` for unit-square stabbing, and `1/3` for guillotine
hardness.

## Evidence bundle

`docs/assets/replacement_81_final_20260712/` contains:

- `data/`: final CSVs, compact source tables, and dataset manifest;
- `analysis/`: generated figures and descriptive CSV/JSON analyses;
- `constructions/`: the three final record renderings;
- `run_artifacts/`: portable best-certificate JSON and SVG pairs for all 81
  configurations, plus their mapping table;
- `audit/`: merged exact-audit outputs;
- `report/`: generated LaTeX macros and tables.

The large raw event streams remain on the corresponding HPC run roots and are
not stored in Git. The compact epoch-history CSV preserves every record change
needed for the report's learning-curve analysis.

## Rebuild

From the repository root, regenerate figures and LaTeX fragments from the
committed compact data:

```bash
python3 scripts/plot_main_matrix_analysis.py \
  docs/assets/replacement_81_final_20260712/data \
  --out-dir docs/assets/replacement_81_final_20260712/analysis

python3 scripts/generate_main_matrix_tex.py \
  docs/assets/replacement_81_final_20260712/data \
  --plot-table-dir docs/assets/replacement_81_final_20260712/analysis \
  --audit-csv docs/assets/replacement_81_final_20260712/audit/audit.csv \
  --out-dir docs/assets/replacement_81_final_20260712/report

latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -cd docs/manuscript/patternboost_81_run_analysis.tex
```

Install the analysis-only Python dependencies with
`python3 -m pip install -r requirements-analysis.txt` when needed.

## Provenance note

The final matrix contains 36 retained cells from the July 9 table and 45
replacement cells from the July 11 component update. Every selected row used a
nominal 24-hour budget, but the replacement regime changed object counts,
population size, and unit-square diversity controls. The report therefore
treats the merged matrix as the final algorithm comparison, not as a pure
one-factor causal ablation.
