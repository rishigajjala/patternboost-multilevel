# Current Results Snapshot

Last audited run date: 2026-07-03, Asia/Dubai.

For the full narrative report with methodology, figures, per-problem
observations, and next steps, see
[PATTERNBOOST_EXPERIMENT_REPORT.md](PATTERNBOOST_EXPERIMENT_REPORT.md).
The formal manuscript-style version is in
[manuscript/patternboost_experiment_report.tex](manuscript/patternboost_experiment_report.tex)
and
[manuscript/patternboost_experiment_report.pdf](manuscript/patternboost_experiment_report.pdf).

## Best Known Values from Current Code Path

| Problem | Best value | Source run | Certificate details |
| --- | ---: | --- | --- |
| `misr` | `1.4` | previous-best warm-start | 14 rectangles |
| `unit_square` | `1.5000000000000004` | 81-row broad run and warm-start | 20-23 squares, `tau_int=4` |
| `guillotine` | `0.3` | previous-best warm-start | 10 rectangles, 3 destroyed |

## NYUAD Jubail Jobs

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
- `epsilon_net` and `graph_separation` are not part of the current three-problem
  scope.
- Checkpoint values are useful live progress, but paper tables should use
  audited `summary.json` rows and verified certificates.
