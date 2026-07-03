#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="${1:-runs/environment_manifest.txt}"
mkdir -p "$(dirname "$OUT")"

{
  echo "created_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  echo "pwd=$PWD"
  echo "python=$(python3 --version 2>&1)"
  echo "git_commit=$(git rev-parse HEAD 2>/dev/null || true)"
  echo "git_status_short_begin"
  git status --short 2>/dev/null || true
  echo "git_status_short_end"
  echo "pip_freeze_begin"
  python3 -m pip freeze 2>/dev/null || true
  echo "pip_freeze_end"
  echo "module_list_begin"
  module list 2>&1 || true
  echo "module_list_end"
} > "$OUT"

echo "wrote $OUT"
