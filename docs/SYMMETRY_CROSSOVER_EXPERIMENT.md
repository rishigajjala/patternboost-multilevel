# Symmetry/crossover component experiment

This experiment tests two ideas adapted from the imported square-stabbing
search without loading any known construction or target answer.

## New representation axis

Each problem receives one fixed-cardinality, symmetry-canonical representation:

- `misr/fixed_symmetry_rectangles`: random rectangle coordinates;
- `unit_square/fixed_symmetry_grid`: distinct grid positions with one fixed side
  length determined by grid resolution;
- `guillotine/fixed_symmetry_packing`: random disjoint rectangles.

Repair preserves the initial object count. Geometry is canonicalized under
translation, horizontal and vertical reflection, and axis exchange. These are
objective-preserving transformations for all three problems.

## New local-search axis

`symmetry_crossover_hillclimb` performs 25 exact-scored proposals. Exact
admissibility under the shared nontriviality constraints is ranked first, then
the objective score; a proposal is retained whenever that lexicographic key
does not decrease. Proposal probabilities are:

- 55%: shift one object by one grid step;
- 25%: move one object to a random location;
- 10%: exchange the y-coordinates or y-intervals of two objects;
- 10%: apply a random objective-preserving planar symmetry.

For the quadratic-program MISR representation, the analogous operations act on
program coefficients, and axis exchange swaps the x/y coefficient blocks.

## Matrix

For each problem, the matrix contains:

- 9 local-search-only cells: 3 existing representations x 1 new local search x
  3 existing surrogates;
- 9 representation-only cells: 1 new representation x 3 existing local
  searches x 3 existing surrogates;
- 3 combined cells: 1 new representation x 1 new local search x 3 existing
  surrogates.

This gives 21 cells per problem and 63 cells overall.

Generate the matrix with:

```bash
PYTHON_BIN=python3 BUDGET_SECONDS=300 \
  bash scripts/make_symmetry_crossover_matrix.sh
```

Generate a Slurm array from it with:

```bash
PYTHONPATH=src python3 -m multilevel.cli make-slurm \
  --matrix runs/symmetry_crossover_matrix.jsonl \
  --out runs/symmetry_crossover_array.slurm \
  --project-dir "$PWD" \
  --results-dir "$PWD/runs/symmetry_crossover_results" \
  --time 00:15:00 \
  --partition compute \
  --cpus-per-task 1 \
  --mem 4G \
  --runner patternboost
```

The first HPC smoke should use `N=12`, `GRID=8`, a small population, and no
model-training event. A longer run should be selected only after all 63 smoke
rows produce valid summaries and exact-audited certificates.
