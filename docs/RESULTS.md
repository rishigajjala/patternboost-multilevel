# Current Results Snapshot

Last audited run date: 2026-07-04, Asia/Dubai.

For the full narrative report with methodology, figures, per-problem
observations, and next steps, see
[PATTERNBOOST_EXPERIMENT_REPORT.md](PATTERNBOOST_EXPERIMENT_REPORT.md).
The formal manuscript-style version is in
[manuscript/patternboost_experiment_report.tex](manuscript/patternboost_experiment_report.tex)
and
[manuscript/patternboost_experiment_report.pdf](manuscript/patternboost_experiment_report.pdf).
The exploratory appendix tasks are summarized separately in
[EXPLORATORY_RESULTS.md](EXPLORATORY_RESULTS.md).

## Best Known Values from Current Code Path

| Problem | Best value | Source run | Certificate details |
| --- | ---: | --- | --- |
| `misr` | `1.4` | previous-best warm-start | 14 rectangles |
| `unit_square` | `1.5000000000000004` | 81-row broad run and warm-start | 20-23 squares, `tau_int=4` |
| `guillotine` | `0.3` | previous-best warm-start | 10 rectangles, 3 destroyed |

## NYUAD Jubail Jobs

### Exploratory Appendix Run

- Slurm job: `16501338`
- Run root: `runs/explore_overnight_20260704_051618`
- Preserved repository snapshot:
  `docs/assets/exploratory_overnight_20260704_051618/`
- Scope: `epsilon_net` and `graph_separation`
- Status: `12/12 COMPLETED|0:0`
- Stderr: `0` nonempty files
- Summaries: `12/12`
- Matrix: `12` rows, `12` unique fresh seeds, no old fixed-seed hits
- Validation: all best certificates verified against summaries

Best rows:

```text
epsilon_net       1.4545454545454546  eps_n11_t4_k3
graph_separation 0.0                 graph_g3_n5_dense
```

The best graph-separation pressure/search score was `1.3845054945054946`
from `graph_g3_n7_motif`, but no exact bounded-grid separation witness was
certified.

### Previous-Best Warm-Start

- Slurm job: `16493282`
- Run root: `runs/hpc_prevbest_12_4h_min8_resume_20260703_111657`
- Status: `12/12 COMPLETED`
- Stderr: `0` nonempty files
- Stop reason: `budget_exhausted` for all 12 rows
- Resume status: all 12 rows resumed from checkpoints

Best rows:

```text
misr         1.4                 triangle_free_rect / lp_dual_pivot / exact_lp_gap_pressure
unit_square 1.5000000000000004  line_square_incidence / coord_mutation / exact_stab_gap_pressure
guillotine  0.3                 rect_direct_disjoint / packing_resize / k_subset_nonseparability
```

### Broad 81-Row Run

- Slurm job: `16492548`
- Run root: `runs/hpc_81_4h_min8_train7_n12_venv_20260703_101409`
- Status: 71 rows completed, 10 guillotine rows hit Slurm wall time
- Stderr: the 10 nonempty stderr files contain only Slurm time-limit messages
- Checkpoints: all 81 rows have checkpoints

The timed-out broad guillotine rows were weaker than the warm-start guillotine
line. They should not be used as clean final table rows unless resumed and
audited.

## Important Caveats

- The square-stabbing-14-9 package is excluded from current evidence.
- `epsilon_net` and `graph_separation` are exploratory appendix tasks. Keep
  them separate from the main three-problem paper table.
- Checkpoint values are useful live progress, but paper tables should use
  audited `summary.json` rows and verified certificates.
