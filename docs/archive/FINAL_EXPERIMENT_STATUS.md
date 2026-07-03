# Final Experiment Status

Updated: 2026-06-25

## Corrected Primary Bundle

The corrected manuscript bundle is:

`runs/final_manuscript_corrected`

Current requested scope: only the first three problems are included in this
official bundle:

- MISR
- Unit-square stabbing
- Recursive guillotine hardness

Exploratory epsilon-net and graph-separation outputs are not part of this
first-three-problem bundle.

It combines:

- MISR main/follow-up/control results from the original successful NYUAD runs.
- Unit-square main/follow-up/control results from the original successful NYUAD runs.
- Corrected guillotine main/control/follow-up results after the guillotine representation and mutation fix.

Row counts:

- Main ablation: 405 rows
  - MISR: 135
  - Unit-square: 135
  - Guillotine: 135 corrected rows
- Controls: 60 rows
  - MISR: 20
  - Unit-square: 20
  - Guillotine: 20 corrected rows
- Follow-up: 90 rows
  - MISR: 30
  - Unit-square: 30
  - Guillotine: 30 corrected rows

Total corrected bundle rows: 555.

## Audit Evidence

Remote NYUAD audit:

- `runs/final_manuscript_corrected/audit/audit.json`
- Rows: 555
- Passed: 555
- Failed: 0

Local independent audit after copying best certificate JSON files back:

- `runs/final_manuscript_corrected/local_audit/audit.json`
- Rows: 555
- Passed: 555
- Failed: 0

## Best Corrected Scores

Main ablation:

- MISR: 1.25
- Unit-square: 1.3333333333333333
- Guillotine: 0.25

Follow-up:

- MISR: 1.25
- Unit-square: 1.3333333333333333
- Guillotine: 0.25

Controls:

- MISR: 1.25
- Unit-square: 1.2000000000000002
- Guillotine: 0.25

## Guillotine Fix Summary

The original guillotine PatternBoost runs were all zero because the representation and repair logic biased candidates toward recursively sliceable layouts. The fix:

- Added a compact five-rectangle guillotine obstruction motif.
- Made `recursive_obstruction_grammar` seed from transformed obstruction motifs instead of unit-cell cross patterns.
- Replaced unit-cell guillotine repair with disjoint-rectangle-preserving repair.
- Extended guillotine mutations to preserve rectangle sizes, add variable-size blockers, resize rectangles, copy motifs, and reinsert obstruction motifs.
- Updated the default guillotine control cell to use `recursive_obstruction_grammar / recursive_gadget_assembly / depth_limited_dp`.
- Added a regression test that the recursive guillotine representation starts with positive exact score.

## Deferred Exploratory Tasks

The primary three-problem ablation, controls, follow-up, report generation, and certificate audits are complete for the corrected bundle.

Per the latest requested scope, the exploratory tasks are deferred and should
not be included in the current result bundle:

- Exploratory graph-separation task has only smoke/local-baseline evidence, not a publication-grade separation search or unconditional non-representability certificate.
- Exploratory epsilon-net task has only smoke/local-baseline evidence, not a publication-grade order-type search for Pach-Woeginger-style constructions.
- Optional high-precision/rational verification for final LP certificates has not been added.
