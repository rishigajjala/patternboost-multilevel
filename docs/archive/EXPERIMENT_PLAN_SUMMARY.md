# Experiment Plan Summary

This is the operational summary of the attached LaTeX experiment plan.

## Main Ablation

There are three publication problems:

1. `misr`: maximize the verified MISR ratio `alpha_lp / alpha_int`.
2. `unit_square`: maximize the verified line-stabbing ratio `tau_int / tau_lp`.
3. `guillotine`: maximize the verified destroyed fraction `1 - saved / n`.

Each problem has three representation choices, three local-search choices, and
three surrogate choices. One seed therefore runs 27 cells per problem and 81
cells total.

## Stages

- `pilot`: 2 seeds, 1 hour per cell; debug only.
- `main`: 5-10 seeds, 3 hours per cell; primary paper tables.
- `followup`: 10 seeds, 12-24 hours per selected cell; record certificates.
- `audit`: deterministic exact verifier reruns on exported certificates.

## Non-Negotiables

- Hard wall-clock budgets.
- Stable run IDs:
  `problem/representation/local/surrogate/seed/budget/gitsha`.
- Exact scorer status must distinguish `optimal`, `timeout`, `numerical`, and
  `invalid`; timeouts never count as low verified scores.
- Every exported result needs a canonical certificate hash.
- Every final paper table entry must link to a certificate.

## Immediate Implementation Order

1. Exact scorers and certificates.
2. Run matrix and logging schema.
3. Baseline local-only search for each problem.
4. Surrogate feature extraction.
5. PatternBoost model training/sampling loop.
6. Plot and table generation.
7. HPC launch scripts.

