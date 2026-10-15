"""Validated paper-run metadata and subprocess execution for the public artifact.

This module deliberately uses only the standard library. Inspecting the matrix
does not require a solver or PyTorch, and does not start a search.
"""
from __future__ import annotations

import csv
import hashlib
import json
import multiprocessing
import secrets
import subprocess
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARTIFACT = Path("docs/assets/replacement_81_final_20260712")
COMPONENT_KEYS = ("problem", "representation", "local_search", "surrogate")
BEST_CONFIGS = {
    "misr": "misr/triangle_free_rect/sequence_pair_pivot/exact_lp_gap_pressure",
    "unit_square": "unit_square/sqstab_exact_grid/symmetry_crossover_hillclimb/exact_stab_gap_pressure",
    "guillotine": "guillotine/rect_direct_disjoint/witness_breaking/depth_limited_dp",
}
COHORT_COUNTS = {"20750a588a5b": 36, "6f80dfec1a16": 42, "87326f25dbec": 3}


def config_id(row: dict[str, Any]) -> str:
    return "/".join(str(row[key]) for key in COMPONENT_KEYS)


def _indexed(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {}
    for record in records:
        key = record.get("config_id") or config_id(record)
        if key in result:
            raise ValueError(f"Duplicate configuration in {label}: {key}")
        result[key] = record
    if len(result) != 81:
        raise ValueError(f"{label} must contain exactly 81 configurations; found {len(result)}")
    return result


def _expect(row: dict[str, Any], key: str, expected: Any, label: str) -> None:
    if key not in row or row[key] != expected:
        raise ValueError(f"{label}: {key} must be {expected!r}, found {row.get(key)!r}")


def validate_paper_rows(
    rows: list[dict[str, Any]],
    seeds: list[dict[str, Any]],
    final_rows: list[dict[str, Any]],
) -> None:
    """Reject incomplete, duplicated, or inconsistent published runtime evidence."""
    matrix = _indexed(rows, "runtime matrix")
    seed_records = _indexed(seeds, "seed manifest")
    final = _indexed(final_rows, "final CSV")
    if set(matrix) != set(seed_records) or set(matrix) != set(final):
        raise ValueError("Runtime matrix, seed manifest, and final CSV configurations differ")
    common = {
        "iterations": 1_000_000, "budget_seconds": 86_400,
        "exact_every": 5, "model_samples": 16, "model_epochs": 3,
        "block_size": 128, "checkpoint_every": 1, "control_mode": "patternboost",
    }
    counts: Counter[str] = Counter()
    for cid, row in matrix.items():
        seed_record, final_row = seed_records[cid], final[cid]
        if config_id(row) != cid or config_id(seed_record) != cid:
            raise ValueError(f"Component fields disagree with configuration ID: {cid}")
        seed = row.get("rng_seed")
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError(f"{cid}: rng_seed must be an exact integer in [0, 2**63)")
        _expect(seed_record, "rng_seed_decimal", str(seed), cid)
        _expect(row, "run_id", final_row["run_id"], cid)
        _expect(row, "git_commit", seed_record["git_commit"], cid)
        _expect(seed_record, "certificate_hash", final_row["certificate_hash"], cid)
        _expect(row, "population", int(final_row["population_size"]), cid)
        cohort = row["git_commit"][:12]
        if cohort not in COHORT_COUNTS:
            raise ValueError(f"{cid}: unknown historical cohort {cohort}")
        counts[cohort] += 1
        if cohort == "20750a588a5b":
            expected = dict(n=8, grid=8, population=32, elite=6, train_every=7,
                            initial_pool_size=32, immigrants_per_generation=0,
                            preserve_resolution_diversity=False, stage="main")
        elif cohort == "6f80dfec1a16":
            square = row["problem"] == "unit_square"
            expected = dict(n=20 if square else 12, grid=16 if square else 8,
                            population=16, elite=4, train_every=10,
                            initial_pool_size=16, immigrants_per_generation=0,
                            preserve_resolution_diversity=False, stage="main")
        else:
            _expect(row, "problem", "unit_square", cid)
            expected = dict(n=20, grid=16, population=32, elite=12, train_every=10,
                            initial_pool_size=128, immigrants_per_generation=4,
                            preserve_resolution_diversity=True, stage="followup")
        for key, value in {**common, **expected}.items():
            _expect(row, key, value, cid)
        saved = seed_record["runtime_settings"]
        for row_key, saved_key in {
            "population": "population_size", "elite": "elite_size",
            "n": "n", "grid": "grid", "train_every": "train_every",
            "exact_every": "exact_every", "iterations": "iterations",
            "budget_seconds": "budget_seconds", "model_samples": "model_samples",
            "checkpoint_every": "checkpoint_every", "stage": "stage",
        }.items():
            _expect(row, row_key, saved[saved_key], cid)
        hparams = saved["model_hparams"]
        _expect(row, "model_epochs", hparams["epochs"], cid)
        _expect(row, "block_size", hparams["block_size"], cid)
        for key in ("initial_pool_size", "immigrants_per_generation", "preserve_resolution_diversity"):
            if key in saved:
                _expect(row, key, saved[key], cid)
        # Four historical cells never reached a model-training call. Their
        # requested model was auto, so do not invent an observed model type.
        model = hparams.get("model_kind_latest") or hparams["model_kind_requested"]
        _expect(row, "model_kind", model, cid)
    if dict(counts) != COHORT_COUNTS:
        raise ValueError(f"Historical cohort counts must be 36/42/3, found {dict(counts)}")


def load_paper_rows(root: str | Path) -> list[dict[str, Any]]:
    data = Path(root) / ARTIFACT / "data"
    rows = [json.loads(line) for line in (data / "final_81_runtime.jsonl").read_text().splitlines() if line.strip()]
    manifest = json.loads((data / "final_81_seeds.json").read_text())
    with (data / "final_81_runs.csv").open(newline="") as handle:
        final_rows = list(csv.DictReader(handle))
    validate_paper_rows(rows, manifest["records"], final_rows)
    return rows


def select_rows(
    rows: list[dict[str, Any]], *, problem: str | None = None,
    seed: int | None = None, fresh_seeds: bool = False,
    iterations: int | None = None, budget_seconds: int | None = None,
    checkpoint_every: int | None = None, model_kind: str | None = None,
) -> list[dict[str, Any]]:
    """Copy validated historical rows, then apply explicit rerun overrides."""
    if seed is not None and (problem is None or fresh_seeds):
        raise ValueError("An explicit seed requires one problem and cannot accompany fresh seeds")
    if seed is not None and (type(seed) is not int or not 0 <= seed < 2**63):
        raise ValueError("Seed must be an integer in [0, 2**63)")
    for name, value in (("iterations", iterations), ("budget_seconds", budget_seconds), ("checkpoint_every", checkpoint_every)):
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError(f"{name} must be a positive integer")
    if model_kind is not None and model_kind not in {"transformer", "ngram"}:
        raise ValueError("Choose transformer or an explicitly non-paper ngram run")
    if problem is not None:
        if problem not in BEST_CONFIGS:
            raise ValueError(f"Unknown problem: {problem}")
        chosen = [row for row in rows if config_id(row) == BEST_CONFIGS[problem]]
        if len(chosen) != 1:
            raise ValueError(f"Expected exactly one headline configuration for {problem}; found {len(chosen)}")
    else:
        chosen = rows
    selected = []
    for original in chosen:
        row = dict(original)
        if seed is not None:
            row["rng_seed"] = seed
        elif fresh_seeds:
            row["rng_seed"] = secrets.randbits(63)
        for key, value in (("iterations", iterations), ("budget_seconds", budget_seconds), ("checkpoint_every", checkpoint_every)):
            if value is not None:
                row[key] = value
        # Keep historical auto requests unless the caller explicitly overrides
        # them. The driver requires PyTorch before any paper-guided execution.
        if model_kind is not None:
            row["model_kind"] = model_kind
        selected.append(row)
    return selected


def certificate_entries(root: str | Path) -> list[tuple[str, Path]]:
    """Require every paper cell's certificate and validate its stored hash."""
    root = Path(root)
    rows = load_paper_rows(root)
    cert_root = root / ARTIFACT / "run_artifacts"
    with (cert_root / "artifact_mapping.csv").open(newline="") as handle:
        mapping = _indexed(list(csv.DictReader(handle)), "certificate mapping")
    with (root / ARTIFACT / "data/final_81_runs.csv").open(newline="") as handle:
        final = _indexed(list(csv.DictReader(handle)), "final CSV")
    if set(mapping) != {config_id(row) for row in rows}:
        raise ValueError("Certificate mapping does not cover the 81 paper configurations")
    entries = []
    for row in rows:
        cid = config_id(row)
        relative = mapping[cid].get("certificate_path")
        if not relative:
            raise FileNotFoundError(f"Missing certificate mapping for {cid}")
        path = (cert_root / relative).resolve()
        if not path.is_relative_to(cert_root.resolve()) or not path.is_file():
            raise FileNotFoundError(f"Missing certificate for {cid}: {path}")
        certificate = json.loads(path.read_text())
        payload = dict(certificate)
        stored_hash = payload.pop("certificate_hash", None)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        if not (stored_hash == digest == mapping[cid]["certificate_hash"] == final[cid]["certificate_hash"]):
            raise ValueError(f"Certificate hash mismatch for {cid}: {path}")
        if config_id(certificate) != cid:
            raise ValueError(f"Certificate configuration mismatch for {cid}: {path}")
        entries.append((cid, path))
    return entries


@dataclass(frozen=True)
class CellTask:
    index: int
    command: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    log_path: str


@dataclass(frozen=True)
class CellResult:
    index: int
    returncode: int
    error: str = ""


class BatchFailure(RuntimeError):
    def __init__(self, results: list[CellResult]):
        self.results = results
        failed = [result for result in results if result.returncode]
        super().__init__(f"{len(failed)} of {len(results)} cells failed: " + ", ".join(f"{r.index} (exit {r.returncode})" for r in failed))


def run_cell(task: CellTask) -> CellResult:
    """Top-level, spawn-picklable worker; never turns a failed cell into success."""
    try:
        with Path(task.log_path).open("w", encoding="utf-8") as log:
            result = subprocess.run(task.command, cwd=task.cwd, env=task.env, stdout=log, stderr=subprocess.STDOUT)
        return CellResult(task.index, result.returncode)
    except OSError as exc:
        return CellResult(task.index, 125, str(exc))


def run_tasks(tasks: list[CellTask], *, parallel: int = 1) -> list[CellResult]:
    if parallel < 1:
        raise ValueError("parallel must be positive")
    results = []
    if parallel == 1:
        for task in tasks:
            result = run_cell(task)
            results.append(result)
            print(f"Cell {result.index}: {'OK' if result.returncode == 0 else 'FAILED'}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=parallel, mp_context=multiprocessing.get_context("spawn")) as pool:
            pending = {pool.submit(run_cell, task): task.index for task in tasks}
            for future in as_completed(pending):
                try:
                    result = future.result()
                except Exception as exc:
                    result = CellResult(pending[future], 125, str(exc))
                results.append(result)
                print(f"Cell {result.index}: {'OK' if result.returncode == 0 else 'FAILED'}", flush=True)
    results.sort(key=lambda result: result.index)
    if any(result.returncode for result in results):
        raise BatchFailure(results)
    return results
