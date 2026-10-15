#!/usr/bin/env python3
"""Inspect, verify, and rerun the final 81-cell PatternBoost artifact.

Search defaults are the recorded seeds, each cell's historical runtime settings,
and a 24-hour / 1,000,000-generation cap. Use --dry-run to inspect a search first.
This executes the current checkout: recorded source commits are provenance, not
an automatic checkout of historical code. Seed recovery does not establish
identical reruns or robustness across seeds.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from multilevel.paper_artifact import (  # noqa: E402
    ARTIFACT, BEST_CONFIGS, BatchFailure, CellTask, certificate_entries,
    config_id, load_paper_rows, run_tasks, select_rows,
)


def _positive(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("verify", "smoke", "single", "full", "matrix", "figures"))
    parser.add_argument("--problem", choices=tuple(BEST_CONFIGS), default="unit_square", help="Headline configuration for single mode")
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument("--paper-seeds", action="store_true", help="Use recorded paper seeds (the default)")
    seeds.add_argument("--fresh-seeds", action="store_true", help="Generate and save new seeds; this is a new trial")
    seeds.add_argument("--seed", type=int, help="Explicit seed for single mode only")
    parser.add_argument("--iterations", type=_positive, help="Override every selected row's generation cap (default 1000000)")
    parser.add_argument("--budget-seconds", type=_positive, help="Override every selected row's wall-clock budget (default 86400)")
    parser.add_argument("--checkpoint-every", type=_positive, help="Override historical checkpoint interval of 1 generation")
    parser.add_argument("--parallel", type=_positive, default=1, help="Concurrent cells for full/verify (default 1)")
    parser.add_argument("--threads", type=_positive, default=4, help="CPU library threads per cell (default 4)")
    parser.add_argument("--model-kind", choices=("transformer", "ngram"), default=None, help="Explicitly override historical row model modes; ngram is a deviation from the paper's transformer-guided search")
    parser.add_argument("--dry-run", action="store_true", help="Write the single/full matrix and commands without running searches")
    parser.add_argument("--out-root", type=Path, default=ROOT / "runs", help="Parent for a new, uniquely named output directory")
    parser.add_argument("--out", type=Path, help="Explicit new matrix filename for matrix mode; existing files are never overwritten")
    return parser


def subprocess_environment(threads: int) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[name] = str(threads)
    return env


def new_run_root(parent: Path, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = parent.resolve() / f"{label}_{stamp}_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_matrix(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _cli(*args: str) -> tuple[str, ...]:
    return (sys.executable, "-m", "multilevel.cli", *args)


def require_search_model(model_kind: str) -> None:
    if model_kind == "ngram":
        return
    try:
        importlib.import_module("torch")
    except Exception as exc:
        raise RuntimeError(
            "Paper-guided searches require a working PyTorch installation. "
            "Install requirements-torch.txt, or explicitly select --model-kind ngram "
            "for a non-paper sampler. Matrix generation and --dry-run do not require PyTorch."
        ) from exc


def _run_checked(command: tuple[str, ...], env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode:
        raise RuntimeError(f"Command failed with exit {result.returncode}: {' '.join(command)}")


def _execute(tasks: list[CellTask], run_root: Path, parallel: int) -> None:
    try:
        results = run_tasks(tasks, parallel=parallel)
    except BatchFailure as exc:
        _write_json(run_root / "execution_results.json", {"success": False, "cells": [asdict(result) for result in exc.results]})
        raise
    _write_json(run_root / "execution_results.json", {"success": True, "cells": [asdict(result) for result in results]})


def _search(args: argparse.Namespace) -> None:
    rows = select_rows(
        load_paper_rows(ROOT), problem=args.problem if args.mode == "single" else None,
        seed=args.seed, fresh_seeds=args.fresh_seeds, iterations=args.iterations,
        budget_seconds=args.budget_seconds, checkpoint_every=args.checkpoint_every,
        model_kind=args.model_kind,
    )
    execute = args.mode != "matrix" and not args.dry_run
    required_model = args.model_kind or "transformer"
    if execute:
        require_search_model(required_model)
    label = f"single_{args.problem}" if args.mode == "single" else args.mode
    run_root = new_run_root(args.out_root, label)
    matrix_file = args.out.resolve() if args.out else run_root / "matrix.jsonl"
    write_matrix(matrix_file, rows)
    env = subprocess_environment(args.threads)
    tasks = [CellTask(
        index=index,
        command=_cli("patternboost-cell", "--matrix", str(matrix_file), "--index", str(index), "--out-root", str(run_root), "--model-kind", required_model),
        cwd=str(ROOT), env=env, log_path=str(run_root / f"cell_{index:02d}.log"),
    ) for index in range(len(rows))]
    seed_mode = "explicit" if args.seed is not None else "fresh" if args.fresh_seeds else "recorded"
    metadata = {
        "schema": "paper_artifact_rerun_v1", "mode": args.mode,
        "execution": "current_checkout_rerun" if execute else "prepared_without_execution",
        "matrix": str(matrix_file), "seed_mode": seed_mode,
        "model_kind_override": args.model_kind,
        "row_model_kinds": sorted({row["model_kind"] for row in rows}),
        "non_paper_sampler": args.model_kind == "ngram",
        "threads_per_cell": args.threads,
        "parallel": args.parallel if args.mode == "full" else 1,
        "rows": [{"config_id": config_id(row), "rng_seed_decimal": str(row["rng_seed"]),
                  "historical_source_commit": row["git_commit"], "iterations": row["iterations"],
                  "budget_seconds": row["budget_seconds"]} for row in rows],
        "commands": [list(task.command) for task in tasks],
        "notes": [
            "Row run IDs and git_commit values identify historical source records. Execution uses the current checkout.",
            "A recovered seed does not guarantee the same result across environments or demonstrate robustness across seeds.",
            "Runtime overrides are saved in the generated matrix, which takes precedence over underlying CLI defaults.",
            "Default model modes preserve the historical rows, including four auto requests without observed training; paper-guided execution still requires PyTorch.",
        ],
    }
    _write_json(run_root / "run_manifest.json", metadata)
    print(f"Validated {len(rows)} selected paper configurations; seed mode: {seed_mode}.")
    print(f"Matrix: {matrix_file}\nOutputs: {run_root}")
    if args.model_kind == "ngram":
        print("Explicit deviation: ngram sampler; these are not transformer-guided paper runs.")
    if not execute:
        print("Prepared matrix and commands; no searches were run.")
        return
    print("Rerunning with the current checkout and recorded historical settings; results may vary.", flush=True)
    _execute(tasks, run_root, args.parallel if args.mode == "full" else 1)
    summary = run_root / "summary.csv"
    _run_checked(_cli("summary", "--root", str(run_root), "--out", str(summary)), env)
    # A successful subprocess is not enough if it produced no recorded run.
    import csv
    with summary.open(newline="") as handle:
        summaries = list(csv.DictReader(handle))
    if len(summaries) != len(rows):
        raise RuntimeError(f"Expected {len(rows)} result summaries, found {len(summaries)}")
    audit = run_root / "audit"
    audit.mkdir()
    _run_checked(_cli("audit", "--summary", str(summary), "--out", str(audit / "audit.json"), "--csv", str(audit / "audit.csv")), env)
    print(f"Completed and audited {len(rows)} runs. Outputs: {run_root}")


def _verify(args: argparse.Namespace) -> None:
    entries = certificate_entries(ROOT)  # Fails before running if any of 81 are absent.
    run_root = new_run_root(args.out_root, "verify")
    env = subprocess_environment(args.threads)
    tasks = [CellTask(index, _cli("verify", str(path)), str(ROOT), env, str(run_root / f"certificate_{index:02d}.log")) for index, (_cid, path) in enumerate(entries)]
    _execute(tasks, run_root, args.parallel)
    print(f"All {len(entries)} paper certificates passed hash checks and exact re-verification. Logs: {run_root}")


def _smoke(args: argparse.Namespace) -> None:
    run_root = new_run_root(args.out_root, "smoke")
    # smoke performs score-and-verify checks; its CLI does not accept model-kind.
    _run_checked(_cli("smoke", "--out", str(run_root)), subprocess_environment(args.threads))
    print(f"Smoke checks completed. Outputs: {run_root}")


def _figures(args: argparse.Namespace) -> None:
    run_root = new_run_root(args.out_root, "figures")
    data = ROOT / ARTIFACT / "data"
    analysis, report = run_root / "analysis", run_root / "report"
    env = subprocess_environment(args.threads)
    _run_checked((sys.executable, str(ROOT / "scripts/plot_main_matrix_analysis.py"), str(data), "--out-dir", str(analysis)), env)
    _run_checked((sys.executable, str(ROOT / "scripts/generate_main_matrix_tex.py"), str(data), "--plot-table-dir", str(analysis), "--audit-csv", str(ROOT / ARTIFACT / "audit/audit.csv"), "--out-dir", str(report)), env)
    print(f"Figures and tables regenerated: {run_root}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.seed is not None and args.mode != "single":
        parser.error("--seed is supported only with --mode single")
    if args.out is not None and args.mode != "matrix":
        parser.error("--out is supported only with --mode matrix")
    if args.dry_run and args.mode not in {"single", "full", "matrix"}:
        parser.error("--dry-run is supported for single/full; matrix never runs searches")
    if args.mode not in {"single", "full", "matrix"} and (
        args.fresh_seeds or args.seed is not None or args.iterations is not None
        or args.budget_seconds is not None or args.checkpoint_every is not None
        or args.model_kind is not None
    ):
        parser.error("Search overrides apply only to single/full/matrix modes")
    try:
        if args.mode in {"single", "full", "matrix"}:
            _search(args)
        elif args.mode == "verify":
            _verify(args)
        elif args.mode == "smoke":
            _smoke(args)
        else:
            _figures(args)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
