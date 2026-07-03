#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

VENV="${VENV:-/scratch/$USER/pb_multilevel_venv}"
PYTHON_MODULE="${PYTHON_MODULE:-python/3.11.3}"
INSTALL_TORCH="${INSTALL_TORCH:-1}"
PIP_CACHE_DIR="${PIP_CACHE_DIR:-/scratch/$USER/pip-cache}"
MANIFEST="${MANIFEST:-runs/hpc_environment_manifest.txt}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if command -v module >/dev/null 2>&1; then
  module purge || true
  module load "$PYTHON_MODULE"
fi

"$PYTHON_BIN" -m venv "$VENV"
source "$VENV/bin/activate"
export PIP_CACHE_DIR

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e . -r requirements.txt
if [ "$INSTALL_TORCH" = "1" ]; then
  python3 -m pip install -r requirements-torch.txt
fi

scripts/freeze_environment.sh "$MANIFEST"
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/hpc_smoke

echo "scratch venv ready: $VENV"
