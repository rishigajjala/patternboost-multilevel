#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m multilevel.cli smoke --out runs/smoke

