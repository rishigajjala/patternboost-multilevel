from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


SUMMARY_FIELDS = [
    "run_id",
    "stage",
    "problem",
    "representation",
    "local_search",
    "surrogate",
    "control_mode",
    "rng_seed",
    "budget_seconds",
    "iterations",
    "completed_iterations",
    "stop_reason",
    "best_exact_score",
    "time_to_best",
    "best_certificate_path",
    "best_rendering_path",
    "best_certificate_hash",
    "num_exact_calls",
    "num_exact_timeouts",
    "num_invalid_samples",
    "num_repaired_samples",
    "num_duplicates",
    "num_model_train_calls",
    "num_model_samples",
    "num_model_samples_valid",
    "fallback_floor_attempts",
    "fallback_floor_used",
    "effective_train_every",
    "effective_model_samples",
    "effective_local_search",
    "num_exports",
    "event_stream",
    "checkpoint_path",
    "checkpoint_every",
    "resumed_from_checkpoint",
    "elapsed_seconds",
    "return_code",
]


def collect_summaries(root: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(root).rglob("summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("schema") != "run_summary_v1":
            continue
        row = {field: data.get(field) for field in SUMMARY_FIELDS}
        row["summary_path"] = str(path)
        rows.append(row)
    return rows


def write_summary_csv(root: str | Path, out_path: str | Path) -> Path:
    rows = collect_summaries(root)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = SUMMARY_FIELDS + ["summary_path"]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return target
