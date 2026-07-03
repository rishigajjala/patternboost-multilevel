# Manuscript Requirements Status

This file tracks implementation status against the attached experiment plan.

## Implemented

- Stable component registry for the 81-cell main ablation matrix.
- Matrix generator with run IDs.
- Exact standalone scorers and certificate verifiers for:
  - MISR LP-gap search
  - unit-square stabbing LP-gap search
  - recursive guillotine hardness
  - bounded-grid rectangle-vs-square/segment exploratory search
  - finite epsilon-net lower-bound exploratory search
- Certificate JSON hashing and `multilevel verify`.
- SVG renderings for all five certificate schemas.
- Exact-scored local-only controls for all five problem types.
- Component-aware surrogate/local-search loop for the three main ablation
  problems.
- PatternBoost runner for the three main ablation problems, including
  model retraining, model-generated samples, surrogate ranking, local mutation,
  exact audits, JSONL model/candidate events, model artifact exports, best
  certificates, renderings, and JSON checkpoint/resume support.
- Hard wall-clock budget handling for PatternBoost, component search, and
  local-only runs. Positive budgets stop at iteration/generation boundaries,
  summaries record `completed_iterations` and `stop_reason`, and PatternBoost
  checkpoints preserve this metadata for resumable HPC jobs.
- Representation-specific initial generators for all nine registered main
  representations, including graph-realized and clique-layer MISR starts,
  line-incidence and threshold-layer unit-square starts, and sequence-pair and
  recursive-obstruction guillotine starts.
- Representation-aware repair/metadata refresh for all nine registered main
  representations, used after local mutations and model decoding before
  surrogate/exact scoring.
- Component-specific local mutations now include edge-alignment, motif-copy,
  cluster/layer shifts, line-alignment, cut-blocker, sequence-order, and
  recursive gadget moves in addition to simple coordinate jitter/add/delete.
- First-class control matrix generation and runner modes for local-only,
  model-only/weak-local, shuffled-label, and known-seed controls.
- JSONL event streams, `run_summary_v1` summaries, summary CSV collection, and
  paper-facing report/plot generation.
- Bootstrap mean confidence intervals, ECDF plots, component heatmaps,
  surrogate-vs-exact scatter plots, and candidate-diversity plots in the report
  generator.
- Solver-method metadata, runtime provenance, dependency-version metadata, and
  pinned requirement files for reproducibility.
- Independent certificate audit command and shell wrapper for checking best
  certificates from result summaries.
- Shell entry points for one cell, one problem baseline, full matrix search,
  full matrix PatternBoost, full controls, full matrix baseline, environment
  capture, audit, and smoke tests.
- Slurm array script generation for matrix rows, defaulting to the PatternBoost
  runner.
- NYUAD/Jubail helper scripts for Conda environment preparation, safe pilot and
  control array submission, sanity-slice submission, resume submission, and
  post-HPC summary/report/audit collection.
- Scratch-backed NYUAD Python virtualenv setup for faster installs on Jubail,
  with optional Torch installation for transformer model-training runs.
- Follow-up matrix selection from pilot summary CSVs, including top-k cells per
  problem, deterministic score-based ranking, selection metadata export, and
  follow-up matrix/Slurm generation and array submission wrappers.

## Partially Implemented

- Representation, local-search, and surrogate component names are respected by
  the runner. Non-direct representations now have distinct initial generators,
  mutation-aware repair, and refreshed payload metadata, but the mature
  grammar/decoder loops are still simplified compared with the full manuscript
  design.
- The PatternBoost runner can train a tiny transformer when PyTorch is
  available and otherwise use the n-gram fallback. It has not yet been tuned or
  validated at manuscript scale.
- Exploratory graph separation currently proves bounded-grid infeasibility only.
  It does not prove unconditional non-representability in the mixed
  square/segment class.
- Epsilon-net verification is exact for the finite input, but the search
  generator is still a simple random baseline rather than an engineered
  order-type mutation loop.

## Still Missing For Full Manuscript Completion

- Publication-grade transformer hyperparameters and model ablations beyond the
  current runnable PatternBoost loop.
- Publication-grade implementations of the non-direct representation families,
  especially full graph-realization algorithms, grammar decoders, and
  sequence-pair/recursive-obstruction optimization beyond the current repair
  and mutation layer.
- Strong problem-specific local-search acceptance schedules and scorer-guided
  neighborhoods for each registered local-search name.
- Publication-scale pilot/main/follow-up runs on the required seed budgets.
- Real pilot-derived follow-up selection after the NYUAD pilot results are
  collected; the selector is implemented, but no HPC pilot result bundle exists
  yet in this workspace.
- Independent audit rerun in a clean separate environment after the final HPC
  result bundle is copied back.
- Optional high-precision/rational verification for final LP certificates near
  important thresholds.
