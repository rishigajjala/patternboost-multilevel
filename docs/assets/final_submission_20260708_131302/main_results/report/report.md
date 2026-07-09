# PatternBoost Multi-Level Run Report

Generated from structured `run_summary_v1` files.

## Artifacts

- `component_table`: `runs/final_submission_20260708_131302/main_results/report/component_table.csv`
- `best_scores_svg`: `runs/final_submission_20260708_131302/main_results/report/best_scores.svg`
- `ecdf_scores_svg`: `runs/final_submission_20260708_131302/main_results/report/ecdf_scores.svg`
- `component_heatmap_svg`: `runs/final_submission_20260708_131302/main_results/report/component_heatmap.svg`
- `surrogate_exact_scatter_svg`: `runs/final_submission_20260708_131302/main_results/report/surrogate_exact_scatter.svg`
- `candidate_diversity_svg`: `runs/final_submission_20260708_131302/main_results/report/candidate_diversity.svg`

## Component Table

| Problem | Representation | Local search | Surrogate | Control | Runs | Stops | Iter | Best | Mean | 95% CI | Median | Median time | Hash |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| guillotine | rect_direct_disjoint | packing_resize | depth_limited_dp | patternboost | 1 | 1 | 5476 |  |  | [, ] |  |  | `` |
| guillotine | rect_direct_disjoint | packing_resize | first_cut_obstruction | patternboost | 1 | 1 | 5911 |  |  | [, ] |  |  | `` |
| guillotine | rect_direct_disjoint | packing_resize | k_subset_nonseparability | patternboost | 1 | 1 | 5230 |  |  | [, ] |  |  | `` |
| guillotine | rect_direct_disjoint | recursive_gadget_assembly | depth_limited_dp | patternboost | 1 | 1 | 3198 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 11583.4 | `cafee06cf67a83b6ec8eff27e3e7b1dfbbd6ba155441ae880b936b2c3a706b13` |
| guillotine | rect_direct_disjoint | recursive_gadget_assembly | first_cut_obstruction | patternboost | 1 | 1 | 5016 | 0.181818 | 0.181818 | [0.181818, 0.181818] | 0.181818 | 9605.97 | `86f4e7a3a292ea566df19e0712042bcc91ba46773ea4d589bfa2c937e35f01d4` |
| guillotine | rect_direct_disjoint | recursive_gadget_assembly | k_subset_nonseparability | patternboost | 1 | 1 | 956 | 0.125 | 0.125 | [0.125, 0.125] | 0.125 | 12626.4 | `58514687b163df8a9196bc6cd0601a7851b6eb5cf1bf9dddc45f4eccb845a01d` |
| guillotine | rect_direct_disjoint | witness_breaking | depth_limited_dp | patternboost | 1 | 1 | 1656 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 17791.2 | `1614be0d4ec7aa0ff012970033f80788d25becf3013fe77cf4d88bf1788b8b00` |
| guillotine | rect_direct_disjoint | witness_breaking | first_cut_obstruction | patternboost | 1 | 1 | 3660 | 0.0833333 | 0.0833333 | [0.0833333, 0.0833333] | 0.0833333 | 5893.42 | `3d48857d384d61250aa5b3722a24ec8aaf791e5b34a40648bfd90ca59f438f0c` |
| guillotine | rect_direct_disjoint | witness_breaking | k_subset_nonseparability | patternboost | 1 | 1 | 569 | 0.125 | 0.125 | [0.125, 0.125] | 0.125 | 9909.04 | `ce3f0f58b3a0e43faf73eae2542bbdc0d053b4df6ea5725f3939d84bf8d68e72` |
| guillotine | recursive_obstruction_grammar | packing_resize | depth_limited_dp | patternboost | 1 | 1 | 1991 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 10.13 | `0c1e3b671859768a48f27ece16b4367845c663aaad2777cba8412ea5e32dd969` |
| guillotine | recursive_obstruction_grammar | packing_resize | first_cut_obstruction | patternboost | 1 | 1 | 3865 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 10.1002 | `e3cb2b35826051356ebba1f04d6778d9768a688729e00320d40437de5dad5eb1` |
| guillotine | recursive_obstruction_grammar | packing_resize | k_subset_nonseparability | patternboost | 1 | 1 | 609 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 10.1255 | `205b23b0bb9a631dabccb2f330d14759f6dbf7faa3097a17839066dc5782c9aa` |
| guillotine | recursive_obstruction_grammar | recursive_gadget_assembly | depth_limited_dp | patternboost | 1 | 1 | 1564 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 9.98042 | `4486d67e054d6325bc857925b0ff2cda7d1ae92172da16b6ece3fac306436590` |
| guillotine | recursive_obstruction_grammar | recursive_gadget_assembly | first_cut_obstruction | patternboost | 1 | 1 | 3496 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 10.0119 | `9915248eaafd532c4cc963c938dc1f6ed429af26ff1f9108a129b677ab413708` |
| guillotine | recursive_obstruction_grammar | recursive_gadget_assembly | k_subset_nonseparability | patternboost | 1 | 1 | 539 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 9.6382 | `e40054a9c4760503dd16ed350750430eb9f581eb8a5f449d01b24404cee2f27d` |
| guillotine | recursive_obstruction_grammar | witness_breaking | depth_limited_dp | patternboost | 1 | 1 | 1852 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 9.58474 | `97082a9b95205a5edd69257c841ae91cb023713123e15a068f1bbda6a71cbe6d` |
| guillotine | recursive_obstruction_grammar | witness_breaking | first_cut_obstruction | patternboost | 1 | 1 | 3795 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 9.58452 | `302da887a6123a41e3af93afd572945af04cd2b1ff8966a5f93389b7064723bb` |
| guillotine | recursive_obstruction_grammar | witness_breaking | k_subset_nonseparability | patternboost | 1 | 1 | 517 | 0.25 | 0.25 | [0.25, 0.25] | 0.25 | 9.58104 | `bbfa56b3e3f761244782b8ffa871c782edabc53cbac9f6c19ba8eb40a68f541a` |
| guillotine | sequence_pair_packing | packing_resize | depth_limited_dp | patternboost | 1 | 1 | 6306 |  |  | [, ] |  |  | `` |
| guillotine | sequence_pair_packing | packing_resize | first_cut_obstruction | patternboost | 1 | 1 | 6873 |  |  | [, ] |  |  | `` |
| guillotine | sequence_pair_packing | packing_resize | k_subset_nonseparability | patternboost | 1 | 1 | 3873 | 0.230769 | 0.230769 | [0.230769, 0.230769] | 0.230769 | 529.248 | `34be647714928b1b4c696ea641ba2ec13638bfd3bac5aeb6c382ee13c7941934` |
| guillotine | sequence_pair_packing | recursive_gadget_assembly | depth_limited_dp | patternboost | 1 | 1 | 2901 | 0.227273 | 0.227273 | [0.227273, 0.227273] | 0.227273 | 15541.4 | `9f9afc1719481f8d283bdc192046c29009fae0ac6106c42317558a88b8a4985b` |
| guillotine | sequence_pair_packing | recursive_gadget_assembly | first_cut_obstruction | patternboost | 1 | 1 | 5206 | 0.181818 | 0.181818 | [0.181818, 0.181818] | 0.181818 | 59.4899 | `050425d364acb66a4fe71692e3c28262466aa4bb9b2b7ac2669bc2d0ac80242a` |
| guillotine | sequence_pair_packing | recursive_gadget_assembly | k_subset_nonseparability | patternboost | 1 | 1 | 796 | 0.190476 | 0.190476 | [0.190476, 0.190476] | 0.190476 | 12907.9 | `7a15325ceba669c75201452893688413a157ce58cb242843ac418d56f3d6c03d` |
| guillotine | sequence_pair_packing | witness_breaking | depth_limited_dp | patternboost | 1 | 1 | 1849 | 0.222222 | 0.222222 | [0.222222, 0.222222] | 0.222222 | 21510.2 | `2ea2ad398f3ec5c410dad9fcaa73bbc7efd71fe384dc762d50e851e857739847` |
| guillotine | sequence_pair_packing | witness_breaking | first_cut_obstruction | patternboost | 1 | 1 | 3701 | 0.142857 | 0.142857 | [0.142857, 0.142857] | 0.142857 | 934.55 | `0c94a41aac337e5995f700b6dec04a86fc4d2849324c72b912decfd3b7eb1bda` |
| guillotine | sequence_pair_packing | witness_breaking | k_subset_nonseparability | patternboost | 1 | 1 | 516 | 0.166667 | 0.166667 | [0.166667, 0.166667] | 0.166667 | 12310.1 | `ed76bebeecfa664961bf23274562cbe90ee534c147280b7cf0a0419fe58d651a` |
| misr | endpoint_sequence_pair | lp_dual_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 9176 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 273.486 | `c78bb3c814924c73e0aeccbe38afc1ae92340108ac2291e81868c5c9a9126568` |
| misr | endpoint_sequence_pair | lp_dual_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 5734 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 400.287 | `41b107aae8e1c00260d51235a95ba9167dbb58f7994947619049c2f188162924` |
| misr | endpoint_sequence_pair | lp_dual_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 8060 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 9.54205 | `fc7eabe097b57cbc41ff916b0e6d4a3ef2b50963a4f573a9525f689cf9ee194a` |
| misr | endpoint_sequence_pair | program_coeff_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 6544 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 550.025 | `417aa9b08b35e616cd031763c035de05cdd5d70170e6efe5817068506602a999` |
| misr | endpoint_sequence_pair | program_coeff_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 4229 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 4795.14 | `201d5c73a70300b9a468b0aec5ff170860e23668e2906fee77b063d237d746d7` |
| misr | endpoint_sequence_pair | program_coeff_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 4712 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 3304.76 | `cb4acf05cffaba7aab79a547bb5921dd0be9b5cee46245a0a97afa28ce924dca` |
| misr | endpoint_sequence_pair | sequence_pair_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 5914 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 1465.87 | `62823977aeae97e609267cf0125ebed8acdd9ea510db1c9062f3cced72313894` |
| misr | endpoint_sequence_pair | sequence_pair_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 3257 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 1619.76 | `6fdb6f538c8c58d98623ff118a76931548159a9303422b4e8a13602f5daa4041` |
| misr | endpoint_sequence_pair | sequence_pair_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 6314 | 1.16667 | 1.16667 | [1.16667, 1.16667] | 1.16667 | 4028.86 | `1a5a62764278693b51d79ff23e29b99ec9a6b510d9ec1c253eb74689dd358f3f` |
| misr | quadratic_program_rectangles | lp_dual_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 5869 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 2926.67 | `6550ee2171109a1cd582d69561bafe10e63d82186bad21f54def42072c545f2d` |
| misr | quadratic_program_rectangles | lp_dual_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 5804 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 861.76 | `a10b58f643df3c2bda94ecfafb38a1bad53a39967e567e1eee68727c711c1a9d` |
| misr | quadratic_program_rectangles | lp_dual_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 5776 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 4465 | `12f5bf1c1884906e5daf3847d82399f0f97bedb7639834b1064bc22ac9ebaff6` |
| misr | quadratic_program_rectangles | program_coeff_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 5818 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 244.494 | `d6375452f5614d3bfda94dd9f5b2728c0512d040bea3733b6ae1de960a4cfb57` |
| misr | quadratic_program_rectangles | program_coeff_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 5762 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 1183.63 | `9c80f0ba762dd9f5f8c1a7507708c8093ba2d081b9d347ad4bdf7b9a19e20c72` |
| misr | quadratic_program_rectangles | program_coeff_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 5729 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 2186.84 | `8d024aa4b5ff77690ff67d9f50c04497322145141201cb218525df564a108ea6` |
| misr | quadratic_program_rectangles | sequence_pair_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 5882 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 2634.55 | `6e9a520612a3095507e2a4916938ffafae48d64b830656ab2da29c1e3c2a6186` |
| misr | quadratic_program_rectangles | sequence_pair_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 5869 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 5596.7 | `299507e85d0a13e9790d5ec2c423f17e302ef1aaba21ae5b61e798f7a4720e6a` |
| misr | quadratic_program_rectangles | sequence_pair_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 5867 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 661.165 | `087f669d9f0f744c6c6f59edf242b9ee77301acdad0c1ff785e6d66255787769` |
| misr | triangle_free_rect | lp_dual_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 5994 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 347.409 | `8ff778283b7a83ccfe240535e0bb7a199c4eea11f3a1bd0f850243c0d4c8eacb` |
| misr | triangle_free_rect | lp_dual_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 7001 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 20723.3 | `4703215739598f3325bcceb8cec1f1c058c7b1895fcdb7ef3665034150932255` |
| misr | triangle_free_rect | lp_dual_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 6416 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 674.281 | `401e9ee2167ec1a8296c9ca4068a616467f91b253ec848825f08b96e54731f0a` |
| misr | triangle_free_rect | program_coeff_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 6248 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 185.814 | `e26ee113be6e1cb4ba9b595c74a51f554aec492c3da2003900f8ac0c93aaaa42` |
| misr | triangle_free_rect | program_coeff_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 6804 | 1.125 | 1.125 | [1.125, 1.125] | 1.125 | 57.8754 | `9655fdb7e1ea6577941498742a0210f59ee338616f6b993114cb0025c78c5b1e` |
| misr | triangle_free_rect | program_coeff_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 6337 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 9514.65 | `309632efb0724c3f999a31de9fc616b92a22dfe3f80875767bcfb7990d2052f9` |
| misr | triangle_free_rect | sequence_pair_pivot | exact_lp_gap_pressure | patternboost | 1 | 1 | 4985 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 4860.11 | `a7fb6984571170bac512da8f6cbf943cb28961e7a1a7bffa76f630654a08ca70` |
| misr | triangle_free_rect | sequence_pair_pivot | graph_conflict_proxy | patternboost | 1 | 1 | 6937 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 449.09 | `3aef4ddeda962fd9e8c0f934c39244ae97cc7f69dff45c52c4383f98114d1436` |
| misr | triangle_free_rect | sequence_pair_pivot | triangle_free_exact_gap_pressure | patternboost | 1 | 1 | 6322 | 1.375 | 1.375 | [1.375, 1.375] | 1.375 | 3750.78 | `c0d510db44314050b02186d2300a378318e19e2e232c799069ac0fcca1e4e3d5` |
| unit_square | line_square_incidence | coord_mutation | exact_stab_gap_pressure | patternboost | 1 | 1 | 6214 | 1.42857 | 1.42857 | [1.42857, 1.42857] | 1.42857 | 2876.25 | `1186caa4a6426cba0ea92554aa85585910b4fb522058a8cf9ea955754ed8c1a9` |
| unit_square | line_square_incidence | coord_mutation | greedy_partial_lp_bitset | patternboost | 1 | 1 | 5216 | 1.19048 | 1.19048 | [1.19048, 1.19048] | 1.19048 | 4723.16 | `54a1cc11b4c69567fadf98f3212fe1bb7601af83eeabb72006c7b62b738c8cbc` |
| unit_square | line_square_incidence | coord_mutation | incidence_statistics | patternboost | 1 | 1 | 6826 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 918.796 | `0495465f6c4788dd9dc6b6c697a72a9bb7e1d054548b91cdb02022e7692f46f5` |
| unit_square | line_square_incidence | primal_dual_lines | exact_stab_gap_pressure | patternboost | 1 | 1 | 5475 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 2064.42 | `986055e4fef2598fdf56c1d4fd42162ca668e897d2f36ac247659e0a9a16fefd` |
| unit_square | line_square_incidence | primal_dual_lines | greedy_partial_lp_bitset | patternboost | 1 | 1 | 5365 | 1.23077 | 1.23077 | [1.23077, 1.23077] | 1.23077 | 2995.85 | `03ef267da6bdf752009a902ce20389e680c11ed78c599f3e259db4c48238d0ac` |
| unit_square | line_square_incidence | primal_dual_lines | incidence_statistics | patternboost | 1 | 1 | 6002 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 408.169 | `0d3b9d580559bf4a929e3e315ad1da3d04b64bb440e9c1d5e420a67fc03522b3` |
| unit_square | line_square_incidence | sqstab_local_hillclimb | exact_stab_gap_pressure | patternboost | 1 | 1 | 4859 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 11259.9 | `a5a852f779c3302927ee0e503c880c351ac754f269e4f9d6a3938fbdce3f5e0e` |
| unit_square | line_square_incidence | sqstab_local_hillclimb | greedy_partial_lp_bitset | patternboost | 1 | 1 | 4686 | 1.30435 | 1.30435 | [1.30435, 1.30435] | 1.30435 | 10796.5 | `88b19da2c99d06b5fd9404159f8b63494c00b4241ff58bdfbb6966d71f3ecec9` |
| unit_square | line_square_incidence | sqstab_local_hillclimb | incidence_statistics | patternboost | 1 | 1 | 5727 | 1.30435 | 1.30435 | [1.30435, 1.30435] | 1.30435 | 1506.88 | `1b433a8ac0c88213d4a5a54bfa7dbdb5286f19d41aebab8b46cf777d2480f66d` |
| unit_square | sqstab_exact_grid | coord_mutation | exact_stab_gap_pressure | patternboost | 1 | 1 | 6615 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 1385.19 | `4a30a2a9d64390eda7870a5db47db2d2ab2c39cc3a7286866f3d52b42005016a` |
| unit_square | sqstab_exact_grid | coord_mutation | greedy_partial_lp_bitset | patternboost | 1 | 1 | 6304 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 127.356 | `dc34f8d1c27ce8a69bc6feff5debb6535527d9a2b04880f05848400f1f0294a6` |
| unit_square | sqstab_exact_grid | coord_mutation | incidence_statistics | patternboost | 1 | 1 | 6987 | 1.30435 | 1.30435 | [1.30435, 1.30435] | 1.30435 | 1968.19 | `ea0d77208b85c9657276514d263943c312bedf07e2c1fac34747998c92523217` |
| unit_square | sqstab_exact_grid | primal_dual_lines | exact_stab_gap_pressure | patternboost | 1 | 1 | 6243 | 1.42857 | 1.42857 | [1.42857, 1.42857] | 1.42857 | 219.972 | `796fe7d68852dbd00f0a77a7b0a56807ee7ee386fc3cc17657e184f8b1b3d230` |
| unit_square | sqstab_exact_grid | primal_dual_lines | greedy_partial_lp_bitset | patternboost | 1 | 1 | 6112 | 1.30435 | 1.30435 | [1.30435, 1.30435] | 1.30435 | 5986.16 | `0dc2e999f70d139d7a9f73efc97faddf4adcdbe18ffe88a0a9706068516dc225` |
| unit_square | sqstab_exact_grid | primal_dual_lines | incidence_statistics | patternboost | 1 | 1 | 7017 | 1.31579 | 1.31579 | [1.31579, 1.31579] | 1.31579 | 2509.4 | `658e0989a5898025c0246beb568e060d1f7d02e27e49d6dda72e78c9a370ec53` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | exact_stab_gap_pressure | patternboost | 1 | 1 | 6590 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 16848.7 | `55cdf9a8c18c838da9ce5d0b588ee57741c43497f2a721ee6d3ffadcb7c8c05a` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | greedy_partial_lp_bitset | patternboost | 1 | 1 | 6385 | 1.33333 | 1.33333 | [1.33333, 1.33333] | 1.33333 | 5548.13 | `33fc1a034a1828e886a5b7141c7d64246bb7c4ab60d484fd80cf2f2c513a4ef7` |
| unit_square | sqstab_exact_grid | sqstab_local_hillclimb | incidence_statistics | patternboost | 1 | 1 | 6965 | 1.31579 | 1.31579 | [1.31579, 1.31579] | 1.31579 | 9967.63 | `c38fc7c879bab81ed9523ba10fe09dc06c2f300e676f39ad7c87a11d16ee3197` |
| unit_square | square_direct | coord_mutation | exact_stab_gap_pressure | patternboost | 1 | 1 | 6760 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 440.85 | `07df854342692ee46a97ed0acc97cb0603485435b523b3845c66640856654276` |
| unit_square | square_direct | coord_mutation | greedy_partial_lp_bitset | patternboost | 1 | 1 | 6628 | 1.23077 | 1.23077 | [1.23077, 1.23077] | 1.23077 | 395.2 | `911a0344f7b1936ea0a096f827951a2cc82f19872ffbb6ac054065bc2115834d` |
| unit_square | square_direct | coord_mutation | incidence_statistics | patternboost | 1 | 1 | 7816 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 714.122 | `f1407937ceea3402d86860e13c2cd5eb00be73ec71ae537a15c99e3003e27e8b` |
| unit_square | square_direct | primal_dual_lines | exact_stab_gap_pressure | patternboost | 1 | 1 | 6853 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 178.925 | `628d03ed3c9bd48b4ebbf2cb5de33593bc2021f09e1e0559457bebd9c8d3530d` |
| unit_square | square_direct | primal_dual_lines | greedy_partial_lp_bitset | patternboost | 1 | 1 | 6580 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 16114.9 | `f2f0a1871a185e3d67d625d68e568d4173c25934cc0ce2aaac4574042974b2df` |
| unit_square | square_direct | primal_dual_lines | incidence_statistics | patternboost | 1 | 1 | 7883 | 1.25 | 1.25 | [1.25, 1.25] | 1.25 | 2914 | `a9cd00f75bcee489b36830624d3889389eee1c130ba66b44532578d42606b521` |
| unit_square | square_direct | sqstab_local_hillclimb | exact_stab_gap_pressure | patternboost | 1 | 1 | 6959 | 1.5 | 1.5 | [1.5, 1.5] | 1.5 | 169.444 | `57518dac9c8d29395a6c32d84aa302ebbca2146b8fe55305a8c8514d5cd63b36` |
| unit_square | square_direct | sqstab_local_hillclimb | greedy_partial_lp_bitset | patternboost | 1 | 1 | 6447 | 1.2963 | 1.2963 | [1.2963, 1.2963] | 1.2963 | 17804.5 | `215a8ee8239eab02946d605d96a09847b472f516094c4d2a112664ba7677f3d1` |
| unit_square | square_direct | sqstab_local_hillclimb | incidence_statistics | patternboost | 1 | 1 | 7064 | 1.31579 | 1.31579 | [1.31579, 1.31579] | 1.31579 | 10150.8 | `4b6f5e8f3bb698a838c677e583aff3172802261ae6e277a069b9f67cde15d2ff` |
