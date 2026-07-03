# Experiment Matrix

The current main experiment has no repeated seed axis. Each generated matrix
row receives one fresh random `rng_seed` automatically.

## Main Matrix

```text
3 problems x 3 representations x 3 local searches x 3 surrogates = 81 rows
```

Generate it:

```bash
scripts/make_main_matrix.sh
```

The output is `runs/main_81_matrix.jsonl`.

## Problems and Components

### MISR

Representations:

- `endpoint_sequence_pair`
- `triangle_free_rect`
- `quadratic_program_rectangles`

Local searches:

- `sequence_pair_pivot`
- `lp_dual_pivot`
- `program_coeff_pivot`

Surrogates:

- `exact_lp_gap_pressure`
- `triangle_free_exact_gap_pressure`
- `graph_conflict_proxy`

### Unit-Square Stabbing

Representations:

- `square_direct`
- `line_square_incidence`
- `sqstab_exact_grid`

Local searches:

- `coord_mutation`
- `primal_dual_lines`
- `sqstab_local_hillclimb`

Surrogates:

- `greedy_partial_lp_bitset`
- `exact_stab_gap_pressure`
- `incidence_statistics`

### Guillotine

Representations:

- `rect_direct_disjoint`
- `sequence_pair_packing`
- `recursive_obstruction_grammar`

Local searches:

- `packing_resize`
- `recursive_gadget_assembly`
- `witness_breaking`

Surrogates:

- `first_cut_obstruction`
- `depth_limited_dp`
- `k_subset_nonseparability`

## Controls

The control matrix has 9 rows:

```text
3 problems x 3 control modes = 9 rows
```

Control modes:

- `local_only`
- `model_only_weak_local`
- `shuffled_label`

Generate it:

```bash
PYTHONPATH=src python3 -m multilevel.cli control-matrix \
  --stage controls \
  --budget-seconds 14400 \
  --problem misr \
  --problem unit_square \
  --problem guillotine \
  --out runs/control_9_matrix.jsonl
```

## Nontrivial Size Gates

The PatternBoost training filter rejects tiny generated examples:

- `misr`: at least 8 rectangles
- `unit_square`: at least 8 squares and exact certificates should meet the
  current stabbing-cover pressure gate
- `guillotine`: at least 8 rectangles and at least 2 destroyed rectangles when
  that certificate field is present

The CLI flag `--n` can raise the minimum. For example, `--n 12` means at least
12 items, not at least 8.

