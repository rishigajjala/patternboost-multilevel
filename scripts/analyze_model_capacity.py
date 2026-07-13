#!/usr/bin/env python3
"""Join model-capacity matrix rows to summaries and write a compact comparison."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _summary_by_run_id(root: Path) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for path in root.rglob("summary.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        run_id = str(data.get("run_id") or "")
        if run_id:
            data["summary_path"] = str(path)
            summaries[run_id] = data
    return summaries


def _number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _format_score(value: float | None) -> str:
    return "missing" if value is None else f"{value:.6f}"


def _format_count(value: Any) -> str:
    return "missing" if value in {None, ""} else str(int(value))


def _format_seconds(value: Any) -> str:
    return "missing" if value in {None, ""} else f"{float(value):.1f}"


def build_rows(matrix: list[dict[str, Any]], summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in matrix:
        summary = summaries.get(str(spec["run_id"]), {})
        rows.append(
            {
                "problem": spec["problem"],
                "selection_rank": spec["selection_rank"],
                "representation": spec["representation"],
                "local_search": spec["local_search"],
                "surrogate": spec["surrogate"],
                "experiment_arm": spec["experiment_arm"],
                "reference_score": spec["reference_score"],
                "best_exact_score": summary.get("best_exact_score"),
                "stop_reason": summary.get("stop_reason", "missing"),
                "completed_iterations": summary.get("completed_iterations"),
                "elapsed_seconds": summary.get("elapsed_seconds"),
                "num_exact_calls": summary.get("num_exact_calls"),
                "num_model_train_calls": summary.get("num_model_train_calls"),
                "model_train_seconds": summary.get("model_train_seconds"),
                "max_num_training_texts": summary.get("max_num_training_texts"),
                "latest_model_num_parameters": summary.get("latest_model_num_parameters"),
                "num_model_samples": summary.get("num_model_samples"),
                "num_model_samples_valid": summary.get("num_model_samples_valid"),
                "best_certificate_path": summary.get("best_certificate_path"),
                "summary_path": summary.get("summary_path"),
                "run_id": spec["run_id"],
            }
        )

    compact_scores = {
        (row["problem"], row["selection_rank"]): _number(row["best_exact_score"])
        for row in rows
        if row["experiment_arm"] == "compact"
    }
    for row in rows:
        compact = compact_scores.get((row["problem"], row["selection_rank"]))
        score = _number(row["best_exact_score"])
        row["score_delta_vs_compact"] = None if compact is None or score is None else score - compact
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["problem"]), int(row["selection_rank"]))
        pairs.setdefault(key, {})[str(row["experiment_arm"])] = row

    better = tied = worse = incomplete = 0
    lines = [
        "# Model-capacity check",
        "",
        "The compact and scaled arms use the same geometry, search operators, exact-scoring cadence,",
        "model-sample count, and wall-clock budget. The scaled intervention jointly increases the",
        "initial corpus, training archive, and transformer capacity. The rows use independently",
        "generated random states, so this is a descriptive comparison rather than a paired-seed",
        "experiment.",
        "",
        "| Problem | Rank | Configuration | Compact score | Scaled score | Delta | Compact gen. | Scaled gen. | Compact train s | Scaled train s |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in sorted(pairs):
        arms = pairs[key]
        compact = arms.get("compact")
        scaled = arms.get("scaled")
        compact_score = _number(None if compact is None else compact["best_exact_score"])
        scaled_score = _number(None if scaled is None else scaled["best_exact_score"])
        if compact_score is None or scaled_score is None:
            incomplete += 1
            delta = None
        else:
            delta = scaled_score - compact_score
            if delta > 1e-9:
                better += 1
            elif delta < -1e-9:
                worse += 1
            else:
                tied += 1
        row = compact or scaled or {}
        config = f"{row.get('representation')}/{row.get('local_search')}/{row.get('surrogate')}"
        lines.append(
            f"| {key[0]} | {key[1]} | `{config}` | {_format_score(compact_score)} | "
            f"{_format_score(scaled_score)} | {_format_score(delta)} | "
            f"{_format_count(None if compact is None else compact['completed_iterations'])} | "
            f"{_format_count(None if scaled is None else scaled['completed_iterations'])} | "
            f"{_format_seconds(None if compact is None else compact['model_train_seconds'])} | "
            f"{_format_seconds(None if scaled is None else scaled['model_train_seconds'])} |"
        )

    lines.extend(
        [
            "",
            f"Complete comparisons: {better + tied + worse}/9. Scaled better: {better}; "
            f"tied: {tied}; worse: {worse}; incomplete: {incomplete}.",
            "",
            "The primary result is the best new exact verified score. Efficiency comparisons must be",
            "limited to this fixed-budget regime and read alongside completed generations and training",
            "time; the experiment does not isolate architecture size from corpus/archive size.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--results-root", required=True, type=Path)
    parser.add_argument("--out-csv", required=True, type=Path)
    parser.add_argument("--out-md", required=True, type=Path)
    args = parser.parse_args()

    matrix = _read_jsonl(args.matrix)
    if len(matrix) != 18:
        raise SystemExit(f"expected 18 capacity rows, found {len(matrix)}")
    rows = build_rows(matrix, _summary_by_run_id(args.results_root))
    write_csv(rows, args.out_csv)
    write_markdown(rows, args.out_md)
    print(f"wrote {args.out_csv} and {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
