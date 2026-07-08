#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = [
    "root",
    "run_id",
    "problem",
    "representation",
    "local_search",
    "surrogate",
    "control_mode",
    "generation",
    "rank",
    "source_type",
    "surrogate_score",
    "exact_score",
    "best_exact_score",
    "candidate_id",
    "event_path",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _event_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("events.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if event.get("schema") != "candidate_event_v1":
                    continue
                if event.get("best_exact_score") in (None, "") and event.get("exact_score") in (None, ""):
                    continue
                rows.append(
                    {
                        "root": str(root),
                        "run_id": event.get("run_id"),
                        "problem": event.get("problem"),
                        "representation": event.get("representation"),
                        "local_search": event.get("local_search"),
                        "surrogate": event.get("surrogate"),
                        "control_mode": event.get("control_mode"),
                        "generation": event.get("generation"),
                        "rank": event.get("rank"),
                        "source_type": event.get("source_type"),
                        "surrogate_score": event.get("surrogate_score"),
                        "exact_score": event.get("exact_score"),
                        "best_exact_score": event.get("best_exact_score"),
                        "candidate_id": event.get("candidate_id"),
                        "event_path": str(path),
                    }
                )
    return rows


def _summary_fallback_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("summary.json")):
        summary = _load_json(path)
        if not summary or summary.get("schema") != "run_summary_v1":
            continue
        rows.append(
            {
                "root": str(root),
                "run_id": summary.get("run_id"),
                "problem": summary.get("problem"),
                "representation": summary.get("representation"),
                "local_search": summary.get("local_search"),
                "surrogate": summary.get("surrogate"),
                "control_mode": summary.get("control_mode"),
                "generation": summary.get("completed_iterations"),
                "rank": "",
                "source_type": "summary_final",
                "surrogate_score": "",
                "exact_score": summary.get("best_exact_score"),
                "best_exact_score": summary.get("best_exact_score"),
                "candidate_id": summary.get("best_certificate_hash"),
                "event_path": str(path),
            }
        )
    return rows


def write_learning_curves(root: Path, out: Path) -> Path:
    rows = _event_rows(root)
    if not rows:
        rows = _summary_fallback_rows(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract best-score learning curves from PatternBoost event streams.")
    parser.add_argument("root", help="run root containing events.jsonl files")
    parser.add_argument("--out", required=True, help="CSV output path")
    args = parser.parse_args()
    target = write_learning_curves(Path(args.root), Path(args.out))
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
