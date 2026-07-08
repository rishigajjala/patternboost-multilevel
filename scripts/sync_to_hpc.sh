#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

REMOTE="${REMOTE:-sg9396@jubail.abudhabi.nyu.edu}"
REMOTE_DIR="${REMOTE_DIR:-~/patternboost/multi-level}"
DRY_RUN="${DRY_RUN:-0}"

RSYNC_ARGS=(
  -az
  --delete
  --exclude .git
  --exclude __pycache__
  --exclude '*.pyc'
  --exclude '*.egg-info'
  --exclude '.venv*'
  --exclude '.local_artifacts'
  --exclude runs
  --exclude 'runs 2'
  --exclude output
  --exclude tmp
  --exclude .pytest_cache
)

if [ "$DRY_RUN" = "1" ]; then
  RSYNC_ARGS+=(--dry-run --itemize-changes)
fi

ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"
rsync "${RSYNC_ARGS[@]}" ./ "$REMOTE:$REMOTE_DIR/"

echo "synced project to $REMOTE:$REMOTE_DIR"
