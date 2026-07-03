# PatternBoost Three-Problem Strategy Study

Updated: 2026-06-30 19:22 +0400  
Scope: MISR, unit-square stabbing, and guillotine hardness only.  
Excluded: epsilon-net, graph-separation, and all `square-stabbing-14-9` evidence, including 14/9 and 20/13 results.

## Executive Summary

The current evidence says the generic multi-level framework is useful as a diagnostic search harness, but the best path toward meaningful bounds is problem-specific, certificate-shaped search.

| Problem | Best current allowed value | Source | Status |
|---|---:|---|---|
| MISR, unrestricted rectangles | 1.400000 | old 90-run framework | exact finite certificate |
| MISR, triangle-free imported track | 1.185185 | imported rectgap local program | exact finite certificate |
| Unit-square stabbing | 1.500000 | allowed `square_stabbing_code.zip` | exact IP/LP scorer |
| Guillotine, old framework | 0.285714 | old 90-run framework | exact DP certificate |
| Guillotine, imported n=40 | 0.300000 | imported guillotine threshold/DP code | exact saved-count audit |

Current live HPC state at the latest scan:

- `16437465`: old 90-run main array, 81 running.
- `16437466`: old controls, 9 running.
- `16450858`: allowed `square_stabbing_code.zip` 16-hour replacement run, running.
- `16446677`: imported guillotine/MISR batch finished with mixed status: guillotine tasks completed; MISR tasks produced artifacts but some ended by timeout.

The main conclusion is:

1. MISR improved in the generic framework when exact LP-gap pressure was used, but the strongest current unrestricted example is not triangle-free.
2. Unit-square stabbing is much better with a dedicated exact C++ scorer and square-stabbing environment than with the old generic unit-square representation.
3. Guillotine improved when the objective was reformulated as a large-subset nonseparability problem, but the current best is still far from the half-destruction target.

## Current Construction Snapshots

### MISR old-framework best, score 1.40

![MISR old framework best](study_assets/fig_misr_old_best_1p4.png)

Certificate components:

- `n = 34`
- LP value `alpha_lp = 4.2`
- exact integer optimum `alpha_int = 3`
- score `alpha_lp / alpha_int = 1.4`
- representation: `rect_direct`
- local search: `lp_dual_pivot`
- surrogate: `exact_lp_gap_pressure`
- triangle-free: `false`

### MISR imported triangle-free best, score 1.185185

![MISR triangle-free local best](study_assets/fig_misr_tf_local_1p185185.png)

Certificate components:

- `n = 64`
- LP value `lp_value = 32`
- exact independent set `alpha = 27`
- exact gap `32 / 27 = 1.185185`
- triangle-free: `true`
- imported local program track, not the old generic coordinate framework

### Unit-square old-framework best, score 4/3

![Unit-square old framework best](study_assets/fig_unit_square_old_4_3.png)

Certificate components:

- 6 unit squares
- exact integer stabbing value `tau_int = 4`
- LP value `tau_lp = 3`
- score `4/3`
- representation: `line_square_incidence`
- local search: `gadget_layer_mutation`
- surrogate: `threshold_rounding_loss`

### Unit-square allowed imported best, score 1.5

![Allowed square-stabbing best](study_assets/fig_unit_square_allowed_1p5.png)

Certificate components:

- 8 squares, side length 2 in the allowed package convention
- exact IP `3`
- exact LP `2`
- score `3/2 = 1.5`
- hash `8e867b64bde38625`
- source: allowed `square_stabbing_code.zip`

### Guillotine old-framework best, score 2/7

![Guillotine old framework best](study_assets/fig_guillotine_old_2_7.png)

Certificate components:

- `n = 7`
- maximum saved by recursive guillotine DP: `5`
- destroyed: `2`
- exact destroyed fraction `2/7 = 0.285714`
- representation: `rect_direct_disjoint`
- local search: `recursive_gadget_assembly`
- surrogate: `first_cut_obstruction`

### Guillotine imported n=40 best, exact score 0.30

![Guillotine n40 exact best](study_assets/fig_guillotine_n40_0p30.png)

Certificate components:

- `n = 40`
- threshold `k = 21`
- exact maximum saved: `28`
- exact minimum destroyed: `12`
- exact destroyed fraction `12/40 = 0.30`
- target half-destruction condition not met

## Problem 1: MISR LP Gap

### Objective

For a rectangle family `R`, the target score is:

`alpha_lp(R) / alpha_int(R)`

where `alpha_int` is the maximum number of pairwise-disjoint rectangles and `alpha_lp` is the LP relaxation value.

### Strategies Tried

#### 1. Direct rectangle-coordinate search

This is the old generic framework path. It mutates rectangle coordinates directly. The best current certificate came from:

- representation: `rect_direct`
- local search: `lp_dual_pivot`
- surrogate: `exact_lp_gap_pressure`

This produced the best unrestricted MISR score so far: `1.40`.

What worked:

- The exact LP-gap surrogate matters. It directly optimizes the proof objective rather than a graph-density proxy.
- `lp_dual_pivot` worked better than generic jitter/resize because it tends to align rectangles around active LP constraints.
- The search found a small high-gap object with `alpha_int = 3`, which is a useful regime because every LP increment is amplified by the small denominator.

What did not work:

- The best object is not triangle-free.
- Direct coordinate search is fragile: small coordinate changes can collapse or create many intersections at once.
- It can find dense small graph obstructions, but it does not naturally enforce structural graph properties such as triangle-freeness.

Interpretation:

This is currently the strongest certified MISR value, but only for the unrestricted problem. If the paper requires triangle-free MISR, this result is diagnostic, not the final target.

#### 2. Endpoint-sequence-pair representation

This was planned as the better representation in `experiments.tex`. Instead of mutating coordinates directly, each rectangle is encoded by two double-occurrence endpoint sequences `H` and `V`. Decoding gives x- and y-spans.

Why this should help:

- Mutations act on endpoint order rather than raw coordinates.
- It preserves a compact combinatorial geometry.
- Swaps, reversals, block moves, motif refreshes, and lifting are more meaningful than raw coordinate jitter.

Current status:

- Conceptually strong, but the current best verified value still comes from `rect_direct`, not the endpoint-sequence track.
- This means the representation has not yet been paired with a strong enough objective/curriculum, or the current run has not had enough time to expose its advantage.

What to improve:

- Make endpoint-sequence search use exact LP-gap pressure more aggressively on elites.
- Add triangle-free repair or triangle penalty if triangle-free is required.
- Add motif libraries extracted from the 1.40 unrestricted certificate and from the imported triangle-free 1.185 certificate.
- Use sequence lifting only when the lifted object preserves or improves LP dual support density.

#### 3. Imported triangle-free local/program search

This imported track explicitly searches triangle-free rectangle-intersection graphs. Best current result:

- `n = 64`
- `alpha = 27`
- `lp_value = 32`
- gap `32/27 = 1.185185`
- triangle-free: true

What worked:

- It enforces the triangle-free condition.
- The geometry is more globally structured than direct coordinate mutation.
- Exact verification succeeds on the best found examples.

What did not work:

- The gap is much lower than the unrestricted 1.40 result.
- Larger `n` alone did not increase the ratio enough.
- The best triangle-free result is likely dominated by a large denominator: improving from `32/27` requires either a higher LP value without increasing `alpha`, or a smaller exact independent set.

What to improve:

- Search for local gadgets where `alpha` grows slowly under composition.
- Use LP-dual feedback, not just triangle-free feasibility.
- Force repeated fractional patterns: many vertices should carry similar positive LP weights while exact independent sets remain constrained.
- Try hybridizing endpoint-sequence search with triangle-free repair.
- Keep an unrestricted and a triangle-free table separate. Mixing them obscures the scientific message.

### MISR Recommendation

Use two MISR tracks:

1. **Unrestricted record track:** continue exact LP-gap pressure search around the 1.40 certificate and endpoint-sequence variants seeded from it.
2. **Triangle-free track:** continue imported/programmatic triangle-free search, but add LP-dual-guided mutation and composition.

Do not claim the 1.40 result as triangle-free. Do not abandon it either: it is currently the best evidence that the LP-gap machinery is capable of finding nontrivial examples.

## Problem 2: Unit-Square Stabbing

### Objective

For a family of unit squares, the target score is:

`tau_int / tau_lp`

where `tau_int` is the exact minimum number of stabbing lines and `tau_lp` is the LP relaxation.

### Strategies Tried

#### 1. Generic old framework

The old framework searched square lower-left coordinates with representations such as:

- `square_direct`
- `line_square_incidence`
- `threshold_layer_grammar`

The best old-framework result is `4/3`.

What worked:

- `line_square_incidence` is better than raw coordinate search because it biases toward square-line incidence structure.
- `gadget_layer_mutation` can create small examples where the integral cover needs more lines than the LP.

What did not work:

- The old framework is too local. Moving one square at a time rarely constructs a large global integrality-gap certificate.
- The surrogate `threshold_rounding_loss` is only a weak proxy for exact LP/IP gap.
- It found a small six-square certificate, but it did not build the larger structured arrangements needed for stronger ratios.

#### 2. Allowed `square_stabbing_code.zip`

This is now the allowed imported unit-square code path. It contains:

- C++20 exact scorer.
- Standalone `sqstab_cli`.
- Axplorer environment `square_stabbing`.
- exact LP/ILP scoring.
- restartable C++ search/journal.

Best allowed result:

- exact IP `3`
- exact LP `2`
- score `1.5`
- hash `8e867b64bde38625`

What worked:

- Exact C++ scoring is fast enough to evaluate many candidates.
- The code directly optimizes the unit-square stabbing objective.
- It recovered a nontrivial `3/2` construction and is clearly better than the old generic framework's `4/3`.

What did not work:

- The current 16-hour run has not improved beyond `1.5`.
- The run stores compact best metadata and a text instance, but not yet a rich certificate with all LP/IP witnesses and a gallery-ready proof object.
- This allowed package is not the discarded 14/9 staircase package, so it should not be expected to reproduce 14/9 unless we implement equivalent structured generators in this allowed codebase.

### Why Unit-Square Was Bad Before

The old unit-square code was bad because it searched geometry directly and locally. Strong stabbing gaps are not just "some squares in the plane"; they usually come from structured incidence patterns. The old local moves did not naturally preserve or amplify the line-cover obstruction.

The allowed C++ package is better because:

- exact scoring is native to the problem;
- it can run many more candidate evaluations;
- candidates are repaired and scored in the same mathematical model;
- it separates search speed from final exact verification.

### Unit-Square Recommendation

Keep using `square_stabbing_code.zip`, but add structured generators inside that allowed package:

1. Ladder and staircase-like families, without importing the discarded `square-stabbing-14-9` code.
2. Incidence-preserving mutations: move a square only when the relevant critical line set remains large.
3. LP-dual-guided local moves: prefer squares hit fractionally by several active lines.
4. Certificate export: save square coordinates, critical line universe, IP solution, LP primal/dual, hash, and rendering.
5. Axplorer curriculum: start from exact `1.5` examples and train on mutations that preserve IP while lowering LP.

The immediate realistic target is to beat `1.5` within the allowed code path. Without a structured family, the run may keep rediscovering `3/2`.

## Problem 3: Guillotine Hardness

### Objective

For a disjoint rectangle family, the exact score is:

`1 - max_saved / n`

where `max_saved` is the maximum number of rectangles preserved by a recursive guillotine strategy.

Equivalently, for `K = floor(n/2) + 1`, a half-destruction certificate would prove there is no guillotine-separable subset of size `K`.

### Strategies Tried

#### 1. Old generic guillotine framework

The old framework used representations such as:

- `rect_direct_disjoint`
- `sequence_pair_packing`
- `recursive_obstruction_grammar`

The previous fix added:

- a compact obstruction motif;
- disjoint-rectangle-preserving repair;
- recursive gadget assembly;
- motif reinsertion;
- depth-limited DP surrogate.

Best old-framework result:

- `n = 7`
- saved `5`
- destroyed `2`
- exact score `2/7 = 0.285714`

What worked:

- The guillotine-specific motif and disjoint repair fixed the earlier all-zero behavior.
- Recursive gadget assembly creates actual obstructions.
- Even first-cut obstruction found meaningful small examples once the representation was corrected.

What did not work:

- The best old-framework certificate is tiny.
- `first_cut_obstruction` is not the final objective; recursive separability can still save many rectangles.
- Local coordinate moves tend to create visually hard layouts that are still recursively separable.

#### 2. Imported threshold/subset guillotine code

This code reframes the problem around `K`-subset separability:

- For `n = 40`, `K = 21`.
- A successful half-destruction certificate would have zero separable `K`-subsets.
- The exact audit found `max_saved_exact = 28`.
- Therefore exact destroyed fraction is `12/40 = 0.30`.
- `target_met = false`.

What worked:

- The imported code searches the right obstruction: large nonseparable subsets.
- It scales to larger constructions than the old generic DP-first framework.
- The exact audit gives a reliable final number, avoiding confusion between attack upper bounds and proof values.

What did not work:

- The n=40 construction is still far from the half-destruction target.
- `sampled_nonseparable_k_fraction = 1.0` is not enough. A sampled near-pass can still have a large exact saved subset.
- Attack-derived values such as `attack_destroyed_fraction_upper_bound` are not proof scores.

### Why Guillotine Scores Are Still Low

A layout can defeat many simple cuts while still allowing a recursive strategy to save a large subset. The search score based on sampled `K`-subsets can look excellent, but exact DP may find a saved set of size 28 out of 40. That means the candidate is locally hard but globally decomposable.

The key gap is between:

- "many random large subsets are nonseparable"; and
- "every large subset is nonseparable, or exact DP cannot save many rectangles."

The current imported code improved the formulation, but the construction family still leaves recursive escape routes.

### Guillotine Recommendation

The next guillotine work should focus on witness-driven repair:

1. Extract the exact saved set of size 28 from the n=40 audit.
2. Identify the recursive cuts used to save that set.
3. Add blockers specifically across those split lines.
4. Preserve nonseparable cores during mutation.
5. Penalize candidates with large exact or attack-found saved subsets, not only candidates with separable sampled `K`-subsets.
6. Build recursively interlocked cores: every large subset should contain at least one hard core.
7. Run exact DP earlier on promising medium-size candidates to avoid over-optimizing sampled near-misses.

The immediate realistic target is not `0.5`; it is to move from `0.30` to a stable `0.33+` exact destroyed fraction with a certificate that explains why the saved set is forced smaller.

## Cross-Problem Lessons

### What Worked

Problem-specific exact verification worked. The strongest results came when the search target matched the mathematical certificate:

- MISR: exact LP-gap pressure.
- Unit-square: exact IP/LP C++ scorer.
- Guillotine: exact saved-count audit after threshold search.

Structured representations also helped:

- endpoint orders for MISR are conceptually better than raw coordinates;
- square-stabbing needs incidence/staircase-like structure;
- guillotine needs nonseparable cores, not just disjoint random rectangles.

### What Failed

Generic coordinate mutation was not enough. It is useful for smoke tests and small baselines, but it does not reliably build large certificate families.

The weakest recurring pattern is surrogate mismatch:

- Unit-square old surrogate did not preserve the line-cover obstruction.
- Guillotine sampled subset hardness overestimated final exact hardness.
- Triangle-free MISR feasibility did not by itself optimize the LP gap.

### What Should Be Reported in the Paper

Report certified values, not training scores:

- MISR unrestricted: `1.40`, exact certificate, clearly marked non-triangle-free.
- MISR triangle-free: `1.185185`, exact certificate, if triangle-free is important.
- Unit-square: `1.5` from allowed code only.
- Guillotine: `0.30` exact from n=40, with a note that target half-destruction is not met.

The old 90-run matrix should be framed as diagnostic evidence. The paper should not imply that a uniform grid search is the core method for all three problems.

## Priority Improvement Plan

### Highest priority

1. Build certificate export for `square_stabbing_code.zip`.
2. Add structured unit-square generators inside the allowed codebase.
3. For guillotine, turn exact saved-set witnesses into mutation targets.
4. For MISR, split unrestricted and triangle-free tracks cleanly.

### Medium priority

1. Seed endpoint-sequence MISR from the 1.40 rectangle certificate.
2. Mine motifs from high-scoring old-framework MISR certificates.
3. Add LP-dual features to imported triangle-free MISR search.
4. Add guillotine core-cover diagnostics: which small subsets are repeatedly nonseparable?

### Lower priority

1. Continue the full old 90-run arrays for diagnostics.
2. Run more random repeats without changing representation.
3. Tune neural model parameters before improving certificate families.

## Bottom Line

The strongest current results are not coming from "more epochs" alone. They are coming from representing the right mathematical object:

- MISR needs endpoint/order or LP-dual-aware geometry.
- Unit-square needs exact incidence/stabbing structure.
- Guillotine needs threshold nonseparability and exact saved-set feedback.

For the next round, the main engineering objective should be to convert the best search code into certificate-producing code: exact verifier output, construction rendering, solver witnesses, and hashes. That will make the experiments defensible even before the numerical bounds improve.
