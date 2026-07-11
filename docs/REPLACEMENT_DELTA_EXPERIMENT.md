# Replacement 3x3x3 delta experiment

The final table remains a complete 3 x 3 x 3 factorial for each of MISR,
unit-square stabbing, and Guillotine separation. One weak representation and
one weak local search are removed from each old table and replaced by the new
fixed-symmetry representation and symmetry/crossover local search.

Only changed cells are rerun. For each problem, the 12 cells using both a
retained representation and a retained local search are reused from the
completed 24-hour study. The delta contains:

- 6 cells using the new local search with two retained representations;
- 6 cells using the new representation with two retained local searches;
- 3 cells combining the new representation and new local search.

This gives 15 new cells per problem and 45 jobs. The 15 new cells and 12
retained cells reconstruct all 27 cells in each replacement table.

## Removed components

The completed 24-hour 81-cell table in
`docs/assets/main_81_24h_20260709_1623` determines the removals:

- MISR: `endpoint_sequence_pair` and `lp_dual_pivot`;
- unit square: `square_direct` and `primal_dual_lines`;
- Guillotine: `sequence_pair_packing` and `recursive_gadget_assembly`.

MISR's two weaker local searches tied in marginal mean; matched-cell rank
breaks the tie against `lp_dual_pivot`. The two weaker Guillotine
representations were effectively tied in aggregate mean (a difference below
0.0006). `rect_direct_disjoint` is retained because it has the stronger lower
tail and contains the exact 1/3 row; `sequence_pair_packing` is removed.

## Generate the 45-row delta

```bash
PYTHON_BIN=python3 BUDGET_SECONDS=86400 \
  bash scripts/make_replacement_delta_matrix.sh
```

There is no seed-replication axis. Each row begins from fresh random geometry;
the recorded RNG state exists only for provenance and exact replay.

## Successful-probe runtime

The replacement matrix uses the runtime regime from the successful two-hour
symmetry/crossover probe. MISR and Guillotine use `n=12` and grid 8;
unit-square stabbing uses `n=20` and grid 16. MISR and Guillotine use
population 16 and elite size 4. Unit-square rows use population 32 and elite
size 12 so that each available resolution retains multiple search lineages.
Every row uses exact scoring every 5 generations, Transformer training every
10 generations, 16 model samples, 3 model epochs, and checkpointing every
generation. The unit-square regime is the one in which the generic
`sqstab_exact_grid / symmetry_crossover_hillclimb /
exact_stab_gap_pressure` row generated and exactly verified a 20-square
certificate with `tau_int=4`, `tau_lp=13/5`, and gap `20/13`.

The unit-square rows also use an initial pool of 128 candidates, four fresh
immigrants per generation, and resolution-stratified retention over every
available integer side length. These are diversity controls, not target hints:
no side length or score is preferred. Candidates below `tau_int=4` may remain
as parents, while the final certificate gate still rejects them. This avoids
permanently losing a potentially useful coordinate resolution before local
search can improve it. A newest immigrant is temporarily retained in each
resolution island and every retained parent receives a mutation opportunity
before random parent selection resumes.

This is experiment family `replacement_delta_v3_resolution_diverse`. It supersedes
the initial `replacement_delta_v1` launch, whose `n=8`, grid-8 unit-square
rows did not reproduce the successful probe's geometric regime. Because this
runtime differs from the retained 24-hour table, any combined 81-cell analysis
must disclose the size/runtime change rather than treating it as a strictly
component-only ablation.
