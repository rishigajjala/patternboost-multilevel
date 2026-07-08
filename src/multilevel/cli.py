from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multilevel import __version__
from multilevel.audit import audit_summary_csv, audit_summary_root, write_audit_outputs
from multilevel.canonical import attach_certificate_hash, load_json, write_json
from multilevel.components import (
    COMPONENTS,
    CONTROL_MODES,
    DEFAULT_STAGE_BUDGETS,
    build_control_matrix,
    build_matrix,
    fresh_rng_seed,
)
from multilevel.exploratory import run_exploratory_search
from multilevel.followup import build_followup_matrix
from multilevel.gitinfo import git_commit
from multilevel.launch import matrix_row, write_slurm_array
from multilevel.local_only import run_random_exact_baseline
from multilevel.patternboost import run_patternboost
from multilevel.provenance import attach_runtime_provenance
from multilevel.render import render_certificate
from multilevel.report import generate_report
from multilevel.scorers import epsilon_net, graph_separation, guillotine, misr, unit_square
from multilevel.search import run_component_search
from multilevel.summary import write_summary_csv


SCORERS = {
    "misr": misr,
    "unit_square": unit_square,
    "guillotine": guillotine,
    "graph_separation": graph_separation,
    "epsilon_net": epsilon_net,
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def cmd_registry(_: argparse.Namespace) -> int:
    print(json.dumps({k: v.__dict__ for k, v in COMPONENTS.items()}, indent=2, sort_keys=True))
    return 0


def cmd_matrix(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    commit = args.git_commit if args.git_commit is not None else git_commit(cwd)
    budget = args.budget_seconds
    if budget is None:
        budget = DEFAULT_STAGE_BUDGETS.get(args.stage, 0)
    rows = build_matrix(
        stage=args.stage,
        budget_seconds=int(budget),
        git_commit=commit,
        problems=args.problem,
    )
    out = Path(args.out)
    _write_jsonl(out, rows)
    print(f"wrote {len(rows)} rows to {out}")
    return 0


def cmd_control_matrix(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    commit = args.git_commit if args.git_commit is not None else git_commit(cwd)
    budget = args.budget_seconds
    if budget is None:
        budget = DEFAULT_STAGE_BUDGETS.get(args.stage, 0)
    rows = build_control_matrix(
        stage=args.stage,
        budget_seconds=int(budget),
        git_commit=commit,
        problems=args.problem,
        control_modes=args.control_mode,
    )
    out = Path(args.out)
    _write_jsonl(out, rows)
    print(f"wrote {len(rows)} rows to {out}")
    return 0


def cmd_followup_matrix(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    commit = args.git_commit if args.git_commit is not None else git_commit(cwd)
    budget = args.budget_seconds
    if budget is None:
        budget = DEFAULT_STAGE_BUDGETS["followup"]
    rows, selected = build_followup_matrix(
        summary_csv=args.summary,
        stage=args.stage,
        budget_seconds=int(budget),
        git_commit=commit,
        top_k=args.top_k,
        problems=args.problem,
        control_modes=args.control_mode,
        min_runs=args.min_runs,
    )
    if not rows:
        print("no follow-up rows selected from summary", flush=True)
        return 1
    out = Path(args.out)
    _write_jsonl(out, rows)
    if args.selection_out:
        write_json(
            args.selection_out,
            {
                "schema": "followup_selection_v1",
                "summary": args.summary,
                "stage": args.stage,
                "budget_seconds": int(budget),
                "top_k": args.top_k,
                "min_runs": args.min_runs,
                "control_modes": args.control_mode or ["patternboost"],
                "selected_cells": selected,
                "rows": len(rows),
            },
        )
    print(f"selected {len(selected)} cells and wrote {len(rows)} rows to {out}")
    return 0


def _row_out_dir(row: dict[str, Any], out_root: str | Path) -> Path:
    parts = [
        str(row["stage"]),
        str(row["problem"]),
        str(row["representation"]),
        str(row["local_search"]),
        str(row["surrogate"]),
    ]
    control_mode = row.get("control_mode")
    if control_mode:
        parts.insert(1, f"control_{control_mode}")
    return Path(out_root).joinpath(*parts)


def _explore_row_out_dir(row: dict[str, Any], out_root: str | Path, index: int) -> Path:
    problem = str(row["problem"])
    run_id = str(row.get("run_id") or f"row_{index}")
    return Path(out_root) / problem / run_id


def _row_int(row: dict[str, Any], key: str, default: int) -> int:
    value = row.get(key)
    return default if value is None else int(value)


def _row_optional_int(row: dict[str, Any], key: str, default: int | None) -> int | None:
    value = row.get(key)
    return default if value is None else int(value)


def _row_optional_float(row: dict[str, Any], key: str, default: float | None) -> float | None:
    value = row.get(key)
    return default if value is None else float(value)


def _row_rng_seed(row: dict[str, Any]) -> int:
    value = row.get("rng_seed")
    if value is None:
        raise ValueError("matrix row is missing rng_seed")
    return int(value)


def cmd_score(args: argparse.Namespace) -> int:
    instance = load_json(args.input)
    cert = SCORERS[args.problem].score_instance(instance)
    cert = attach_runtime_provenance(cert, Path.cwd())
    cert = attach_certificate_hash(cert)
    write_json(args.out, cert)
    print(f"{args.problem} score={cert['score']} certificate={args.out}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    cert = load_json(args.certificate)
    schema = cert.get("schema")
    if schema == "misr_certificate_v1":
        ok = misr.verify_certificate(cert)
    elif schema == "unit_square_stab_certificate_v1":
        ok = unit_square.verify_certificate(cert)
    elif schema == "guillotine_certificate_v1":
        ok = guillotine.verify_certificate(cert)
    elif schema == "graph_separation_certificate_v1":
        ok = graph_separation.verify_certificate(cert)
    elif schema == "epsilon_net_certificate_v1":
        ok = epsilon_net.verify_certificate(cert)
    else:
        raise SystemExit(f"unknown certificate schema: {schema!r}")
    print("verified" if ok else "verification_failed")
    return 0 if ok else 1


def cmd_render(args: argparse.Namespace) -> int:
    cert = load_json(args.certificate)
    target = render_certificate(cert, args.out)
    print(f"rendered {target}")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    root = _project_root()
    out_dir = Path(args.out) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    examples = {
        "misr": root / "examples" / "misr_small.json",
        "unit_square": root / "examples" / "unit_square_small.json",
        "guillotine": root / "examples" / "guillotine_small.json",
        "graph_separation": root / "examples" / "graph_separation_small.json",
        "epsilon_net": root / "examples" / "epsilon_net_small.json",
    }
    summary = []
    for problem, path in examples.items():
        cert = SCORERS[problem].score_instance(load_json(path))
        cert["tool_version"] = __version__
        cert["created_at"] = datetime.now(timezone.utc).isoformat()
        cert = attach_certificate_hash(cert)
        cert_path = out_dir / f"{problem}.cert.json"
        write_json(cert_path, cert)
        svg_path = out_dir / f"{problem}.svg"
        render_certificate(cert, svg_path)
        ok = SCORERS[problem].verify_certificate(cert)
        summary.append(
            {
                "problem": problem,
                "score": cert["score"],
                "certificate": os.fspath(cert_path),
                "rendering": os.fspath(svg_path),
                "verified": ok,
            }
        )
    write_json(out_dir / "summary.json", {"schema": "smoke_summary_v1", "results": summary})
    print(json.dumps(summary, indent=2))
    return 0 if all(row["verified"] for row in summary) else 1


def cmd_local_only(args: argparse.Namespace) -> int:
    seed = args.seed if args.seed is not None else fresh_rng_seed()
    summary = run_random_exact_baseline(
        problem=args.problem,
        seed=seed,
        iterations=args.iterations,
        out_dir=args.out,
        n=args.n,
        grid=args.grid,
        run_id=args.run_id,
        budget_seconds=args.budget_seconds,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_explore(args: argparse.Namespace) -> int:
    seed = args.seed if args.seed is not None else fresh_rng_seed()
    summary = run_exploratory_search(
        problem=args.problem,
        seed=seed,
        iterations=args.iterations,
        population_size=args.population,
        elite_size=args.elite,
        out_dir=args.out,
        n=args.n,
        grid=args.grid,
        run_id=args.run_id,
        budget_seconds=args.budget_seconds,
        mixed_grid=args.mixed_grid,
        timeout_seconds=args.timeout_seconds,
        threshold=args.threshold,
        k=args.k,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_run_cell(args: argparse.Namespace) -> int:
    row = matrix_row(args.matrix, args.index)
    out_dir = _row_out_dir(row, args.out_root)
    summary = run_random_exact_baseline(
        problem=str(row["problem"]),
        seed=_row_rng_seed(row),
        iterations=_row_int(row, "iterations", args.iterations),
        out_dir=out_dir,
        n=_row_int(row, "n", args.n),
        grid=_row_int(row, "grid", args.grid),
        run_id=str(row["run_id"]),
        budget_seconds=int(row["budget_seconds"]) if row.get("budget_seconds") is not None else None,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_search_cell(args: argparse.Namespace) -> int:
    row = matrix_row(args.matrix, args.index)
    out_dir = _row_out_dir(row, args.out_root)
    summary = run_component_search(
        problem=str(row["problem"]),
        representation=str(row["representation"]),
        local_search=str(row["local_search"]),
        surrogate=str(row["surrogate"]),
        seed=_row_rng_seed(row),
        iterations=_row_int(row, "iterations", args.iterations),
        population_size=_row_int(row, "population", args.population),
        elite_size=_row_int(row, "elite", args.elite),
        exact_every=_row_int(row, "exact_every", args.exact_every),
        out_dir=out_dir,
        n=_row_int(row, "n", args.n),
        grid=_row_int(row, "grid", args.grid),
        run_id=str(row["run_id"]),
        stage=str(row["stage"]),
        budget_seconds=int(row["budget_seconds"]) if row.get("budget_seconds") is not None else None,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_explore_cell(args: argparse.Namespace) -> int:
    row = matrix_row(args.matrix, args.index)
    out_dir = _explore_row_out_dir(row, args.out_root, args.index)
    run_id = str(row.get("run_id") or f"row_{args.index}")
    summary = run_exploratory_search(
        problem=str(row["problem"]),
        seed=_row_rng_seed(row),
        iterations=_row_int(row, "iterations", args.iterations),
        population_size=_row_int(row, "population", args.population),
        elite_size=_row_int(row, "elite", args.elite),
        out_dir=out_dir,
        n=_row_int(row, "n", args.n),
        grid=_row_int(row, "grid", args.grid),
        run_id=run_id,
        budget_seconds=int(row["budget_seconds"]) if row.get("budget_seconds") is not None else None,
        mixed_grid=_row_optional_int(row, "mixed_grid", args.mixed_grid),
        timeout_seconds=_row_optional_float(row, "timeout_seconds", args.timeout_seconds),
        threshold=_row_optional_int(row, "threshold", args.threshold),
        k=_row_optional_int(row, "k", args.k),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_patternboost_cell(args: argparse.Namespace) -> int:
    row = matrix_row(args.matrix, args.index)
    out_dir = _row_out_dir(row, args.out_root)
    control_mode = args.control_mode or str(row.get("control_mode") or "patternboost")
    summary = run_patternboost(
        problem=str(row["problem"]),
        representation=str(row["representation"]),
        local_search=str(row["local_search"]),
        surrogate=str(row["surrogate"]),
        seed=_row_rng_seed(row),
        iterations=_row_int(row, "iterations", args.iterations),
        population_size=_row_int(row, "population", args.population),
        elite_size=_row_int(row, "elite", args.elite),
        exact_every=_row_int(row, "exact_every", args.exact_every),
        train_every=_row_int(row, "train_every", args.train_every),
        model_samples=_row_int(row, "model_samples", args.model_samples),
        model_kind=args.model_kind,
        model_epochs=_row_int(row, "model_epochs", args.model_epochs),
        block_size=_row_int(row, "block_size", args.block_size),
        checkpoint_every=_row_int(row, "checkpoint_every", args.checkpoint_every),
        resume=args.resume,
        control_mode=control_mode,
        out_dir=out_dir,
        n=_row_int(row, "n", args.n),
        grid=_row_int(row, "grid", args.grid),
        run_id=str(row["run_id"]),
        stage=str(row["stage"]),
        budget_seconds=int(row["budget_seconds"]) if row.get("budget_seconds") is not None else None,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    target = write_summary_csv(args.root, args.out)
    print(f"wrote summary CSV to {target}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    result = generate_report(args.summary, args.out_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    if args.summary:
        results = audit_summary_csv(args.summary)
    else:
        results = audit_summary_root(args.root)
    report = write_audit_outputs(results, args.out, args.csv)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2, sort_keys=True))
    return 0 if report["failed"] == 0 else 1


def cmd_make_slurm(args: argparse.Namespace) -> int:
    target = write_slurm_array(
        matrix_path=args.matrix,
        out_path=args.out,
        project_dir=args.project_dir,
        results_dir=args.results_dir,
        time_limit=args.time,
        partition=args.partition,
        cpus_per_task=args.cpus_per_task,
        mem=args.mem,
        runner=args.runner,
        conda_env=args.conda_env,
    )
    print(f"wrote Slurm array script to {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="multilevel")
    sub = parser.add_subparsers(dest="command", required=True)

    registry = sub.add_parser("registry", help="print the component registry")
    registry.set_defaults(func=cmd_registry)

    matrix = sub.add_parser("matrix", help="generate a JSONL run matrix")
    matrix.add_argument("--stage", default="pilot", choices=sorted(DEFAULT_STAGE_BUDGETS))
    matrix.add_argument("--budget-seconds", type=int, default=None)
    matrix.add_argument("--git-commit", default=None)
    matrix.add_argument("--problem", action="append", choices=sorted(COMPONENTS), default=None)
    matrix.add_argument("--out", default="runs/matrix.jsonl")
    matrix.set_defaults(func=cmd_matrix)

    control_matrix = sub.add_parser("control-matrix", help="generate manuscript control rows")
    control_matrix.add_argument("--stage", default="controls", choices=sorted(DEFAULT_STAGE_BUDGETS))
    control_matrix.add_argument("--budget-seconds", type=int, default=None)
    control_matrix.add_argument("--git-commit", default=None)
    control_matrix.add_argument("--problem", action="append", choices=sorted(COMPONENTS), default=None)
    control_matrix.add_argument("--control-mode", action="append", choices=CONTROL_MODES, default=None)
    control_matrix.add_argument("--out", default="runs/control_matrix.jsonl")
    control_matrix.set_defaults(func=cmd_control_matrix)

    followup_matrix = sub.add_parser("followup-matrix", help="select top pilot cells and generate follow-up rows")
    followup_matrix.add_argument("--summary", required=True, help="pilot summary CSV")
    followup_matrix.add_argument("--stage", default="followup", choices=sorted(DEFAULT_STAGE_BUDGETS))
    followup_matrix.add_argument("--budget-seconds", type=int, default=None)
    followup_matrix.add_argument("--git-commit", default=None)
    followup_matrix.add_argument("--problem", action="append", choices=sorted(COMPONENTS), default=None)
    followup_matrix.add_argument("--top-k", type=int, default=3)
    followup_matrix.add_argument(
        "--control-mode",
        action="append",
        choices=["patternboost", "component_search", *CONTROL_MODES],
        default=None,
        help="summary control_mode values eligible for selection; default: patternboost",
    )
    followup_matrix.add_argument("--min-runs", type=int, default=1)
    followup_matrix.add_argument("--selection-out", default=None)
    followup_matrix.add_argument("--out", default="runs/followup_matrix.jsonl")
    followup_matrix.set_defaults(func=cmd_followup_matrix)

    score = sub.add_parser("score", help="score an instance and write a certificate")
    score.add_argument("problem", choices=sorted(SCORERS))
    score.add_argument("input")
    score.add_argument("--out", required=True)
    score.set_defaults(func=cmd_score)

    verify = sub.add_parser("verify", help="recompute a certificate")
    verify.add_argument("certificate")
    verify.set_defaults(func=cmd_verify)

    render = sub.add_parser("render", help="render a certificate to SVG")
    render.add_argument("certificate")
    render.add_argument("--out", required=True)
    render.set_defaults(func=cmd_render)

    smoke = sub.add_parser("smoke", help="run all exact scorers on bundled examples")
    smoke.add_argument("--out", default="runs/smoke")
    smoke.set_defaults(func=cmd_smoke)

    local = sub.add_parser("local-only", help="run an exact-scored random local-only baseline")
    local.add_argument("problem", choices=sorted(SCORERS))
    local.add_argument("--seed", type=int, default=None, help="optional reproducibility seed; omitted means fresh random")
    local.add_argument("--iterations", type=int, default=25)
    local.add_argument("--n", type=int, default=12)
    local.add_argument("--grid", type=int, default=8)
    local.add_argument("--out", required=True)
    local.add_argument("--run-id", default=None)
    local.add_argument("--budget-seconds", type=int, default=None)
    local.set_defaults(func=cmd_local_only)

    explore = sub.add_parser("explore", help="run an exploratory exact-scored elite/mutation search")
    explore.add_argument("problem", choices=["graph_separation", "epsilon_net"])
    explore.add_argument("--seed", type=int, default=None, help="optional reproducibility seed; omitted means fresh random")
    explore.add_argument("--iterations", type=int, default=50)
    explore.add_argument("--population", type=int, default=32)
    explore.add_argument("--elite", type=int, default=6)
    explore.add_argument("--n", type=int, default=8)
    explore.add_argument("--grid", type=int, default=8)
    explore.add_argument("--out", required=True)
    explore.add_argument("--run-id", default=None)
    explore.add_argument("--budget-seconds", type=int, default=None)
    explore.add_argument("--mixed-grid", type=int, default=None)
    explore.add_argument("--timeout-seconds", type=float, default=None)
    explore.add_argument("--threshold", type=int, default=None)
    explore.add_argument("--k", type=int, default=None)
    explore.set_defaults(func=cmd_explore)

    run_cell = sub.add_parser("run-cell", help="execute one matrix row with the current baseline runner")
    run_cell.add_argument("--matrix", required=True)
    run_cell.add_argument("--index", type=int, required=True)
    run_cell.add_argument("--out-root", required=True)
    run_cell.add_argument("--iterations", type=int, default=100)
    run_cell.add_argument("--n", type=int, default=12)
    run_cell.add_argument("--grid", type=int, default=8)
    run_cell.set_defaults(func=cmd_run_cell)

    search_cell = sub.add_parser("search-cell", help="execute one matrix row with component-aware surrogate search")
    search_cell.add_argument("--matrix", required=True)
    search_cell.add_argument("--index", type=int, required=True)
    search_cell.add_argument("--out-root", required=True)
    search_cell.add_argument("--iterations", type=int, default=40)
    search_cell.add_argument("--population", type=int, default=24)
    search_cell.add_argument("--elite", type=int, default=4)
    search_cell.add_argument("--exact-every", type=int, default=5)
    search_cell.add_argument("--n", type=int, default=12)
    search_cell.add_argument("--grid", type=int, default=8)
    search_cell.set_defaults(func=cmd_search_cell)

    explore_cell = sub.add_parser("explore-cell", help="execute one exploratory matrix row")
    explore_cell.add_argument("--matrix", required=True)
    explore_cell.add_argument("--index", type=int, required=True)
    explore_cell.add_argument("--out-root", required=True)
    explore_cell.add_argument("--iterations", type=int, default=50)
    explore_cell.add_argument("--population", type=int, default=32)
    explore_cell.add_argument("--elite", type=int, default=6)
    explore_cell.add_argument("--n", type=int, default=12)
    explore_cell.add_argument("--grid", type=int, default=8)
    explore_cell.add_argument("--mixed-grid", type=int, default=None)
    explore_cell.add_argument("--timeout-seconds", type=float, default=None)
    explore_cell.add_argument("--threshold", type=int, default=None)
    explore_cell.add_argument("--k", type=int, default=None)
    explore_cell.set_defaults(func=cmd_explore_cell)

    patternboost_cell = sub.add_parser("patternboost-cell", help="execute one matrix row with PatternBoost model-guided search")
    patternboost_cell.add_argument("--matrix", required=True)
    patternboost_cell.add_argument("--index", type=int, required=True)
    patternboost_cell.add_argument("--out-root", required=True)
    patternboost_cell.add_argument("--iterations", type=int, default=100)
    patternboost_cell.add_argument("--population", type=int, default=32)
    patternboost_cell.add_argument("--elite", type=int, default=6)
    patternboost_cell.add_argument("--exact-every", type=int, default=5)
    patternboost_cell.add_argument("--train-every", type=int, default=10)
    patternboost_cell.add_argument("--model-samples", type=int, default=16)
    patternboost_cell.add_argument("--model-kind", choices=["auto", "transformer", "ngram"], default="auto")
    patternboost_cell.add_argument("--model-epochs", type=int, default=3)
    patternboost_cell.add_argument("--block-size", type=int, default=128)
    patternboost_cell.add_argument("--checkpoint-every", type=int, default=1)
    patternboost_cell.add_argument("--resume", action="store_true")
    patternboost_cell.add_argument("--control-mode", choices=["patternboost", *CONTROL_MODES], default=None)
    patternboost_cell.add_argument("--n", type=int, default=12)
    patternboost_cell.add_argument("--grid", type=int, default=8)
    patternboost_cell.set_defaults(func=cmd_patternboost_cell)

    summary = sub.add_parser("summary", help="collect run_summary_v1 files into CSV")
    summary.add_argument("--root", default="runs")
    summary.add_argument("--out", default="runs/summary.csv")
    summary.set_defaults(func=cmd_summary)

    report = sub.add_parser("report", help="generate paper-facing tables and simple SVG plots")
    report.add_argument("--summary", default="runs/summary.csv")
    report.add_argument("--out-dir", default="runs/report")
    report.set_defaults(func=cmd_report)

    audit = sub.add_parser("audit", help="verify summary best certificates and write an audit report")
    source = audit.add_mutually_exclusive_group(required=True)
    source.add_argument("--summary", help="summary CSV to audit")
    source.add_argument("--root", help="result root containing run_summary_v1 JSON files")
    audit.add_argument("--out", default="runs/audit/audit.json")
    audit.add_argument("--csv", default="runs/audit/audit.csv")
    audit.set_defaults(func=cmd_audit)

    slurm = sub.add_parser("make-slurm", help="write a Slurm array script for a matrix")
    slurm.add_argument("--matrix", required=True)
    slurm.add_argument("--out", required=True)
    slurm.add_argument("--project-dir", default=".")
    slurm.add_argument("--results-dir", default="runs/hpc")
    slurm.add_argument("--time", default="01:00:00")
    slurm.add_argument("--partition", default="compute")
    slurm.add_argument("--cpus-per-task", type=int, default=1)
    slurm.add_argument("--mem", default="8G")
    slurm.add_argument("--runner", choices=["patternboost", "search", "baseline", "explore"], default="patternboost")
    slurm.add_argument("--conda-env", default=None)
    slurm.set_defaults(func=cmd_make_slurm)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
