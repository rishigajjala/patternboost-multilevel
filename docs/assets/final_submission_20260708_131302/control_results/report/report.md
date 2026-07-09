# PatternBoost Multi-Level Run Report

Generated from structured `run_summary_v1` files.

## Artifacts

- `component_table`: `runs/final_submission_20260708_131302/control_results/report/component_table.csv`
- `best_scores_svg`: `runs/final_submission_20260708_131302/control_results/report/best_scores.svg`
- `ecdf_scores_svg`: `runs/final_submission_20260708_131302/control_results/report/ecdf_scores.svg`
- `component_heatmap_svg`: `runs/final_submission_20260708_131302/control_results/report/component_heatmap.svg`
- `surrogate_exact_scatter_svg`: `runs/final_submission_20260708_131302/control_results/report/surrogate_exact_scatter.svg`
- `candidate_diversity_svg`: `runs/final_submission_20260708_131302/control_results/report/candidate_diversity.svg`

## Component Table

| Problem | Representation | Local search | Surrogate | Control | Runs | Stops | Iter | Best | Mean | 95% CI | Median | Median time | Hash |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| guillotine | recursive_obstruction_grammar | witness_breaking | k_subset_nonseparability | local_only | 1 | 1 | 488 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 8.70053 | `81542ca35d0fe443c3ae3e767aa2e315667fbcadcb54d7dd7d0fb9af65425847` |
| guillotine | recursive_obstruction_grammar | witness_breaking | k_subset_nonseparability | model_only_weak_local | 1 | 1 | 624 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 8.70066 | `3aea887ea4179cfe48f2ca43fae2a8739299480fcc12a45e79a35e9a7789205e` |
| guillotine | recursive_obstruction_grammar | witness_breaking | k_subset_nonseparability | shuffled_label | 1 | 1 | 591 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 8.68975 | `609f637ccab8f3f61845ecda71decc5b9169335f37de5747a5eb43d2266c7bc9` |
| misr | quadratic_program_rectangles | program_coeff_pivot | triangle_free_exact_gap_pressure | local_only | 1 | 1 | 8156 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 546.742 | `b847d3b5add5a25da73228cbb11281ab2e37c5a6a1bcb353723284646f901f8b` |
| misr | quadratic_program_rectangles | program_coeff_pivot | triangle_free_exact_gap_pressure | model_only_weak_local | 1 | 1 | 5971 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 90.784 | `ebce926211381e66399bc3d5749921799a9eb8135f24879cd19894e07c332b78` |
| misr | quadratic_program_rectangles | program_coeff_pivot | triangle_free_exact_gap_pressure | shuffled_label | 1 | 1 | 5839 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 963.688 | `910137ad4cf1b83fb05816d72fa572b3aca555b0816a1b89592015e89f703ed6` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | exact_stab_gap_pressure | local_only | 1 | 1 | 9020 | 1.42857 | 1.42857 | [1.42857, 1.42857] | 1.42857 | 601.524 | `f0532ab306dd9c6788642df297040a071920e2822a9f94576a032534306fcdd1` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | exact_stab_gap_pressure | model_only_weak_local | 1 | 1 | 7552 | 1.42857 | 1.42857 | [1.42857, 1.42857] | 1.42857 | 18286.1 | `c8633f772c6284df644b2407a7c7863377163ffcb38e51c892ee218eddc5d5a8` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | exact_stab_gap_pressure | shuffled_label | 1 | 1 | 6537 | 1.42857 | 1.42857 | [1.42857, 1.42857] | 1.42857 | 745.54 | `3c5712b7a84797d507aaeb754e2e71b4e908ebf045c92e55b7b6450c6040dc4d` |
