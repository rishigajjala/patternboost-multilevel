#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

REMOTE="${REMOTE:-sg9396@jubail.abudhabi.nyu.edu}"
SHA="$(git rev-parse HEAD)"
SHORT="${SHA:0:12}"
REMOTE_DIR="${REMOTE_DIR:-/home/sg9396/patternboost/multi-level-${SHORT}}"
SSH_CONTROL_PATH="${SSH_CONTROL_PATH:-$HOME/.ssh/cm/jubail-codex}"
SSH_ARGS=()
if [ -S "$SSH_CONTROL_PATH" ]; then
  SSH_ARGS=(-S "$SSH_CONTROL_PATH")
fi

if ! git diff --quiet -- . || ! git diff --cached --quiet -- .; then
  echo "tracked working tree changes are present; commit or stash them before final HPC deploy" >&2
  git status --short >&2
  exit 1
fi

echo "deploying git commit $SHA"
echo "remote: $REMOTE"
echo "remote dir: $REMOTE_DIR"
if [ "${#SSH_ARGS[@]}" -gt 0 ]; then
  echo "ssh control socket: $SSH_CONTROL_PATH"
fi

ssh "${SSH_ARGS[@]}" "$REMOTE" "bash -s" -- "$REMOTE_DIR" "$SHA" <<'REMOTE_SETUP'
set -euo pipefail
REMOTE_DIR="$1"
SHA="$2"
TMP_DIR="${REMOTE_DIR}.tmp.$$"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
printf '%s\n' "$TMP_DIR"
REMOTE_SETUP

TMP_DIR="$(ssh "${SSH_ARGS[@]}" "$REMOTE" "bash -s" -- "$REMOTE_DIR" <<'REMOTE_TMP'
set -euo pipefail
REMOTE_DIR="$1"
ls -td "${REMOTE_DIR}.tmp."* 2>/dev/null | head -n 1
REMOTE_TMP
)"

if [ -z "$TMP_DIR" ]; then
  echo "failed to create remote temporary directory" >&2
  exit 1
fi

git archive --format=tar HEAD | ssh "${SSH_ARGS[@]}" "$REMOTE" "tar -xf - -C '$TMP_DIR'"

ssh "${SSH_ARGS[@]}" "$REMOTE" "bash -s" -- "$REMOTE_DIR" "$TMP_DIR" "$SHA" <<'REMOTE_FINALIZE'
set -euo pipefail
REMOTE_DIR="$1"
TMP_DIR="$2"
SHA="$3"
printf '%s\n' "$SHA" > "$TMP_DIR/.deployed_git_commit"
rm -rf "$REMOTE_DIR"
mv "$TMP_DIR" "$REMOTE_DIR"
cd "$REMOTE_DIR"
test "$(cat .deployed_git_commit)" = "$SHA"
echo "deployed $SHA to $REMOTE_DIR"
REMOTE_FINALIZE
