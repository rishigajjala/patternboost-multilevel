# PatternBoost Multi-Level Run Report

Generated from structured `run_summary_v1` files.

## Artifacts

- `component_table`: `runs/final_submission_20260708_131302/record_results/report/component_table.csv`
- `best_scores_svg`: `runs/final_submission_20260708_131302/record_results/report/best_scores.svg`
- `ecdf_scores_svg`: `runs/final_submission_20260708_131302/record_results/report/ecdf_scores.svg`
- `component_heatmap_svg`: `runs/final_submission_20260708_131302/record_results/report/component_heatmap.svg`
- `surrogate_exact_scatter_svg`: `runs/final_submission_20260708_131302/record_results/report/surrogate_exact_scatter.svg`
- `candidate_diversity_svg`: `runs/final_submission_20260708_131302/record_results/report/candidate_diversity.svg`

## Component Table

| Problem | Representation | Local search | Surrogate | Control | Runs | Stops | Iter | Best | Mean | 95% CI | Median | Median time | Hash |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| guillotine | rect_direct_disjoint | packing_resize | k_subset_nonseparability | patternboost | 1 | 1 | 7149 |  |  | [, ] |  |  | `` |
| guillotine | recursive_obstruction_grammar | recursive_gadget_assembly | depth_limited_dp | patternboost | 1 | 1 | 4194 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 8.32821 | `d87ee6a37a67533509da5e5a9925957af82286438b7cc29d8a0a749c59eb3667` |
| guillotine | recursive_obstruction_grammar | witness_breaking | k_subset_nonseparability | patternboost | 1 | 1 | 1577 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 8.35827 | `dd80f2ce40cb0e0229993d439b6f68cdc6aeeb4a876a116f44759cdf066395cf` |
| guillotine | sequence_pair_packing | witness_breaking | k_subset_nonseparability | patternboost | 1 | 1 | 1419 | 0.208333 | 0.208333 | [0.208333, 0.208333] | 0.208333 | 11802.1 | `2900647f7bc98594bd25c6b44456ebc0618cb3b52f54a5a521fce2e4ec35b141` |
| misr | endpoint_sequence_pair | sequence_pair_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 13265 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 1874.65 | `965a7bae5936c3ad5dba0d9b01ddd65f619f5a7ae7048dd8c3760be4041fc379` |
| misr | triangle_free_rect | lp_dual_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 12832 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 1229.98 | `05ab4e3bc75abbde0c78c35b9f938d4d68a00f43df198007cb07c381051510a8` |
| misr | triangle_free_rect | lp_dual_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 12846 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 2009.35 | `2f2dc36dbea7b8c12e3229b782fc9de9f3b97b08e5c1b87e4de41258953243a2` |
| misr | triangle_free_rect | sequence_pair_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 12854 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 303.785 | `bd937de41832ba55ef1110dad5aed087dbf612f7fda02d0a90611193829d0867` |
| unit_square | line_square_incidence | coord_mutation | exact_stab_gap_pressure | patternboost | 1 | 1 | 13144 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 1208.34 | `3a5157dc4cc5d72f154142a44c88aa481dfd86228c52dfd4d780f84ec85ec206` |
| unit_square | line_square_incidence | primal_dual_lines | exact_stab_gap_pressure | patternboost | 1 | 1 | 12408 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 39629.2 | `a59e3459c5b8161eeb2f59dbedfdcde1a156ba81cc05e57e2646070f53e1e2d4` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | exact_stab_gap_pressure | patternboost | 1 | 1 | 15875 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 1087.26 | `7ae2765a4a2575ae69a9be531fea90a5b99f973a8e071a44e250e1c5ca6f2e3c` |
| unit_square | square_direct | coord_mutation | exact_stab_gap_pressure | patternboost | 1 | 1 | 13511 | 1.41176 | 1.41176 | [1.41176, 1.41176] | 1.41176 | 395.145 | `3d892adc252795ec9bcac64ec49f6381faad9bd58fb3740baa28da3be0ed3d6c` |
