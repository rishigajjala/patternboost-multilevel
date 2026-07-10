# Final 81-cell experiment analysis

This directory contains the publication-oriented analysis of the completed
24-hour PatternBoost matrix for MISR, unit-square stabbing, and guillotine
hardness.

## Primary report

- TeX: `docs/manuscript/patternboost_81_run_analysis.tex`
- PDF: `docs/manuscript/patternboost_81_run_analysis.pdf`
- Experimental commit: `20750a588a5b5d8e744689b9efa7538b5eaab26b`
- Slurm array: `16602591`
- Run root: `runs/main_81_24h_20260709_1623`

The report covers all 81 configurations, all strict record trajectories,
component marginals, learning behavior by transformer-training epoch and
search generation, exact certificate renderings, limitations, and the full
81-row appendix.

## Evidence bundle

`docs/assets/main_81_24h_20260709_1623/` contains:

- `analysis/`: figures and derived CSV/JSON analyses;
- `constructions/`: the three best standalone certificates and renderings;
- `postprocess/`: compact trajectories, row metrics, summary, and exact audit;
- `report/`: generated LaTeX macros and tables;
- `run_artifacts/`: all 81 summaries and the saved certificate/rendering set.

The exact audit passed all 81 rows. The compact analysis is suitable for the
committed report; raw event streams remain the source for any future event
schema re-analysis and are intentionally not stored in Git.

## Rebuild

From the repository root, regenerate the committed figures and LaTeX fragments
from the compact evidence bundle:

```bash
python3 scripts/plot_main_matrix_analysis.py \
  docs/assets/main_81_24h_20260709_1623/postprocess \
  --out-dir docs/assets/main_81_24h_20260709_1623/analysis

python3 scripts/generate_main_matrix_tex.py \
  docs/assets/main_81_24h_20260709_1623/postprocess \
  --plot-table-dir docs/assets/main_81_24h_20260709_1623/analysis \
  --audit-csv docs/assets/main_81_24h_20260709_1623/postprocess/audit.csv \
  --out-dir docs/assets/main_81_24h_20260709_1623/report

latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -cd docs/manuscript/patternboost_81_run_analysis.tex
```

Install the analysis-only Python dependencies with
`python3 -m pip install -r requirements-analysis.txt` when needed.

Raw event streams are intentionally excluded from Git. Re-run the compaction
and exact audit only against the preserved HPC run root
`runs/main_81_24h_20260709_1623/main_results`, whose original paths are
recorded in `postprocess/analysis_manifest.json`.
