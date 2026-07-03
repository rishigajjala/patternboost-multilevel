#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONDA_ENV="${CONDA_ENV:-patternboost}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
INSTALL_TORCH="${INSTALL_TORCH:-1}"
MANIFEST="${MANIFEST:-runs/hpc_environment_manifest.txt}"

if command -v module >/dev/null 2>&1; then
  module purge || true
  module load miniconda || true
fi

if ! command -v conda >/dev/null 2>&1 && [ -f /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate ]; then
  # Fallback for Jubail-style centralized Miniconda installs.
  source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is not available; load NYUAD Miniconda first or set up your Python manually" >&2
  exit 1
fi

CONDA_BASE="$(conda info --base 2>/dev/null || true)"
if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
  source "$CONDA_BASE/etc/profile.d/conda.sh"
fi

if conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
  conda activate "$CONDA_ENV"
else
  conda create -y -n "$CONDA_ENV" "python=$PYTHON_VERSION"
  conda activate "$CONDA_ENV"
fi

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .
if [ "$INSTALL_TORCH" = "1" ]; then
  python3 -m pip install -r requirements-torch.txt
else
  python3 -m pip install -r requirements.txt
fi

scripts/freeze_environment.sh "$MANIFEST"
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/hpc_smoke
