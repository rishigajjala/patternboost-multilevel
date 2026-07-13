# Experimental implementation details for the manuscript

This note records settings that can be supported by the final run artifacts
and the three evidence revisions used to assemble the final 81-cell table. It
is intended as a collaborator-facing methods checklist. The row-level source
of truth is `docs/assets/replacement_81_final_20260712`.

## Results and convergence data

- `data/final_81_runs.csv`: one row for each of the 81 final configurations,
  including the exact best score, objective values, certificate hash, time to
  best, model epochs, and portable certificate/rendering paths.
- `data/final_81_epoch_history.csv`: 529 initial, strict-improvement, and final
  endpoint records. This is the compact source for score-versus-epoch plots.
- `data/normalized_learning_curves.csv`: dense normalized curves used by the
  long analysis report.
- `report/table_all_81.tex`: complete manuscript-ready 81-row Appendix A table.
- `analysis/fig_*_27_trajectories_model_epoch.{pdf,png}`: all 27 trajectories
  for each problem.
- `analysis/fig_*_component_slices_model_epoch.svg`: three cleaner
  one-component-at-a-time panels for each problem, centered on its best final
  configuration.

All 81 exported certificates passed the exact post-run audit. The exact best
scores are MISR `3/2`, unit-square stabbing `20/13`, and Guillotine `1/3`.

## Final run conditions

The final table is a complete 3 x 3 x 3 matrix for each problem, but it was
assembled from three runtime cohorts. It is therefore important not to report
the README smoke-test tuple as the final setting.

| Cohort | Rows | n / grid | Population / elite | Initial pool / immigrants | Training interval |
| --- | ---: | --- | --- | --- | --- |
| Retained July 9 matrix | 36 | all problems: 8 / 8; search size 8--24 | 32 / 6 | 32 / 0 | every 7 generations |
| Main replacement July 11 | 42 | MISR and Guillotine: 12 / 8, search size 12--36; unit square: 20 / 16, search size 20--60 | 16 / 4 | 16 / 0 | every 10 generations |
| Unit-square resolution follow-up | 3 | 20 / 16, search size 20--60 | 32 / 12 | 128 / 4 per generation | every 10 generations |

Every cohort used:

- exact elite scoring every 5 generations;
- 16 requested model samples per successful training event;
- 3 transformer epochs per training event;
- block/context length 128;
- checkpointing every generation;
- an application wall-clock budget of 86,400 seconds;
- a safety cap of 1,000,000 search generations.

The application checked the wall-clock budget at generation boundaries. Every
final row stopped with `budget_exhausted`; none reached the iteration cap.
Consequently, elapsed times can exceed 86,400 seconds slightly while the last
generation or exact call finishes.

The shared symmetry/crossover hill climb makes 25 exactly evaluated proposals
per call. Its move mixture is 55% one-step shift, 25% random relocation, 10%
pairwise coordinate/interval exchange, and 10% planar D4 symmetry. A proposal
is retained when its lexicographic exact key is nonworsening. Other local
searches use problem-specific discrete move portfolios rather than one shared
probability vector; their definitions are summarized in the report glossary
and implemented in `src/multilevel/mutations.py`.

## Transformer

The learned generator is a small causal transformer trained from scratch at
each training event:

- 2 `TransformerEncoder` layers used with a causal attention mask;
- 4 attention heads;
- token and positional embedding width 96;
- feed-forward width 384;
- GELU activation and zero dropout;
- character-level tokenization of canonical JSON;
- a vocabulary rebuilt from the current elite archive, with explicit
  `<BOS>`, `<EOS>`, and `<UNK>` symbols;
- context/training block length 128 and generation limit 512 tokens;
- AdamW optimizer, learning rate `3e-4`;
- batch size 32;
- 3 training epochs per call;
- order-8 character n-gram fallback sampler when transformer samples do not
  decode as valid JSON.

There is no fixed global vocabulary size because the vocabulary is rebuilt
from the characters present in the archive at each event.

## Exact verification

No Gurobi or Xpress MP license was used.

- MISR: maximal cliques by Bron--Kerbosch, the fractional clique LP through
  `scipy.optimize.linprog(method="highs")`, and the integral maximum
  independent set through an exact bitset branch-and-bound maximum-clique
  algorithm on the complement graph.
- Unit-square stabbing: critical line patterns are enumerated from interval
  endpoints and open-interval midpoints; the fractional set-cover LP uses the
  same SciPy/HiGHS interface; the integral cover is solved by a custom exact
  branch-and-bound set-cover routine.
- Guillotine: a custom exact recursive dynamic program keyed by rectangle
  subset bitmasks, with memoization over all candidate horizontal and vertical
  cuts at rectangle boundaries and open-interval midpoints.

The search environment pins SciPy 1.13.1 and NumPy 2.0.2. The solver calls set
one HiGHS thread and do not set an independent solver time limit; the enclosing
row budget is the time bound. The certificate verifier tolerance is `1e-8` for
the LP-based problems and zero internally for the combinatorial Guillotine DP.

## Initial populations

Every row starts from fresh pseudorandom geometry. There is no replicated-seed
axis and no warm-started best certificate. A randomly generated RNG seed is
stored only for provenance and replay.

- MISR direct coordinates are integral rectangles. With grid 8, repair clamps
  lower endpoints to 0--9 and upper endpoints to 1--10. Triangle-free and
  quadratic-program representations are decoded and repaired into this domain;
  the quadratic coefficients lie in `[-4,4]` initially.
- Unit-square anchors lie on integer grids: 0--8 for grid 8 and 0--16 for grid
  16. Squares are congruent within each instance. `sqstab_exact_grid` samples a
  common integer side from 1--4; `fixed_symmetry_grid` fixes it to 2; the other
  retained unit-square encodings use side 1 unless repaired metadata specifies
  otherwise.
- Direct Guillotine initializers select disjoint unit cells from an 8 x 8 grid.
  The random fixed packing uses a dynamic square domain of side
  `max(grid+2, 2n)` and samples horizontal bars, vertical bars, and compact
  rectangles before canonicalization. The recursive obstruction grammar
  randomizes the spacings and D4 orientation of seven-rectangle cores and adds
  random filler; it does not inject a saved certificate.

Initial object counts are 8 in the retained cohort, 12 for replacement MISR
and Guillotine, and 20 for replacement unit square. General mutation/repair
allows 8--24, 12--36, or 20--60 objects respectively, except that fixed-count
representations preserve their initial cardinality.

## Unit-square change that produced the final improvement

The successful allowed-code trajectory first reached `32/21 = 1.523809...`
and then the exact final value `20/13 = 1.538461...`; there is no exact 1.55
result in the final 81-cell evidence. The separate `14/9 = 1.555...` value
came from a discarded package and must not be attributed to these runs.

The final three unit-square rows changed only generic diversity controls:

1. `n=20`, grid 16 instead of the failed smaller `n=8`, grid-8 regime;
2. population 32 and elite size 12;
3. 128 independently generated initial candidates;
4. four fresh random immigrants per generation;
5. four resolution islands corresponding to common side lengths 1--4;
6. balanced elite/archive retention across the available resolutions;
7. one temporary newest-immigrant slot per resolution island;
8. every retained parent receives one mutation opportunity before random
   parent reuse.

No target score, known certificate, or preferred side length was injected.

## Software and hardware

The search environment is Python 3.11 with NumPy 2.0.2, SciPy 1.13.1, and
PyTorch 2.8.0. Analysis uses Matplotlib 3.8 or newer, pandas 2.1 or newer, and
PyPDF 5 or newer; those analysis packages were lower-bounded rather than
fully frozen in the repository.

NYUAD's official Jubail documentation lists the standard CPU node as two AMD
EPYC 7742 64-core processors at 2.25 GHz (128 cores total) with 480 GB RAM
(3.75 GB/core). It also notes that small jobs can be scheduled onto legacy
Dalma nodes. The PatternBoost array template requested one task, 4 CPU cores,
and 16 GB RAM per row on the `compute` partition. The archived evidence does
not retain each row's Slurm `NodeList`, so the exact physical CPU model used by
each row should be recovered from `sacct` before claiming that every row ran on
EPYC hardware.

Official specifications:
https://crc-docs.abudhabi.nyu.edu/hpc/training/system.html

## Repository and anonymity

The working public repository is:
https://github.com/rishigajjala/patternboost-multilevel

This URL is not anonymous because its owner is visible. For double-blind
submission, export a clean release snapshot to an anonymous artifact service
or a neutral organization account. A personal-account GitHub stub should not
be described as genuinely anonymous.
