# Exploratory Overnight Snapshot

This directory preserves the compact, git-trackable evidence from the audited
NYUAD Jubail exploratory run.

- Slurm job: `16501338`
- Remote run root: `runs/explore_overnight_20260704_051618`
- Final state: `12/12 COMPLETED|0:0`
- Scope: `epsilon_net` and `graph_separation`
- Full event streams: intentionally not preserved here

Included files:

- `matrix.jsonl`: submitted 12-row exploratory matrix
- `*/summary.json`: per-row final summaries
- `*/certificates/*.json`: exported best certificates
- `*/renderings/*.svg`: exported best renderings
- `final_audit.json`: compact final audit including event-derived pressure
  maxima and health counts

The raw summaries retain absolute remote paths for provenance. For local
inspection, use the sibling certificate and rendering files in this directory.
