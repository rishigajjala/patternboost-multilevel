# Final Results Snapshot

Last audited run date: 2026-07-09, Asia/Dubai.

The final submission run was executed on NYUAD Jubail from deployed commit
`8dd31ca1c8888dff0f1975ccbd38963d73b78b38`.

Remote run root:

```text
/home/sg9396/patternboost/multi-level-8dd31ca1c888/runs/final_submission_20260708_131302
```

Preserved compact repository artifacts:

```text
docs/assets/final_submission_20260708_131302/
```

The formal manuscript-style report is in
[manuscript/patternboost_experiment_report.tex](manuscript/patternboost_experiment_report.tex)
and
[manuscript/patternboost_experiment_report.pdf](manuscript/patternboost_experiment_report.pdf).

## Fresh Final Submission Values

These are the best certified values rediscovered in the fresh final arrays.

| Problem | Best score | Stage | Winning configuration | Certificate |
| --- | ---: | --- | --- | --- |
| `misr` | `1.5` | main | `triangle_free_rect / program_coeff_pivot / triangle_free_exact_gap_pressure` | `docs/assets/final_submission_20260708_131302/certificates/main_misr_1.5.json` |
| `unit_square` | `1.5000000000000004` | main | `line_square_incidence / primal_dual_lines / exact_stab_gap_pressure` | `docs/assets/final_submission_20260708_131302/certificates/main_unit_square_1.5.json` |
| `guillotine` | `0.25` | main | `rect_direct_disjoint / recursive_gadget_assembly / depth_limited_dp` | `docs/assets/final_submission_20260708_131302/certificates/main_guillotine_0.25.json` |

Record follow-up tied the fresh bests:

| Problem | Record score | Winning configuration |
| --- | ---: | --- |
| `misr` | `1.5` | `triangle_free_rect / lp_dual_pivot / triangle_free_exact_gap_pressure` |
| `unit_square` | `1.5000000000000004` | `line_square_incidence / coord_mutation / exact_stab_gap_pressure` |
| `guillotine` | `0.25` | `recursive_obstruction_grammar / recursive_gadget_assembly / depth_limited_dp` |

## Reverified Previous-Best Guillotine Certificate

The repository also preserves a previous-best guillotine certificate with
score `0.3`:

```text
docs/assets/final_submission_20260708_131302/reverified_previous_best/guillotine_0p30_reverification.json
```

It recomputes under the final deployed code as:

```text
n = 10
saved = 7
destroyed = 3
score = 0.3
```

This should be cited as a reverified previous-best certificate, not as a
certificate rediscovered by the fresh final record array.

## Job and Audit Summary

| Stage | Slurm job | Rows | Summaries | Audit passed | Audit failed | Stderr |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| smoke | `16566068` | 3 | 3 | smoke only | smoke only | 0 |
| main | `16566072` | 81 | 81 | 76 | 5 | 0 |
| controls | `16566073` | 9 | 9 | 9 | 0 | 0 |
| record | `16566074` | 12 | 12 | 11 | 1 | 0 |

The failed audit rows are all rows with no `best_certificate_path`. No claimed
certificate failed exact recomputation.

The final learning-curve data used for plots is preserved in compact form at:

```text
docs/assets/final_submission_20260708_131302/plots/learning_curves_by_problem.csv
```

## Exploratory Appendix Run

The separately audited exploratory run remains preserved at:

```text
docs/assets/exploratory_overnight_20260704_051618/
```

Best exploratory rows:

```text
epsilon_net       1.4545454545454546  eps_n11_t4_k3
graph_separation 0.0 exact, 1.3845054945054946 pressure/search
```

These exploratory values are not part of the three-problem main table.

## Reporting Rules

- Use only rows with verified certificate JSON files in manuscript tables.
- Do not use failed audit rows as evidence.
- Keep the reverified guillotine `0.3` result separate from the fresh final
  array table.
- Exclude `square-stabbing-14-9` evidence from current claims.
- Keep `epsilon_net` and `graph_separation` in a separate exploratory appendix.
