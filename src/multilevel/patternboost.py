from __future__ import annotations

import json
import os
import random
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multilevel.canonical import attach_certificate_hash, sha256_obj, write_json
from multilevel.modeling import save_model_artifacts, sample_model, train_model
from multilevel.mutations import mutate_instance
from multilevel.provenance import attach_runtime_provenance
from multilevel.representations import (
    decoded_geometry,
    initial_instance_for_representation,
    repair_instance_for_representation,
)
from multilevel.render import render_certificate
from multilevel.scorers import guillotine, misr, unit_square
from multilevel.surrogates import surrogate_score
from multilevel.tokenizer import instance_to_text


SCORERS = {
    "misr": misr,
    "unit_square": unit_square,
    "guillotine": guillotine,
}

LARGE_EXAMPLE_CONSTRAINTS: dict[str, dict[str, int]] = {
    "misr": {"min_items": 8},
    "unit_square": {"min_items": 8, "min_tau_int": 4},
    "guillotine": {"min_items": 8, "min_destroyed": 2},
}


def _model_artifact_keep() -> int:
    raw = os.environ.get("PATTERNBOOST_MODEL_ARTIFACT_KEEP", "1")
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def _prune_model_artifacts(model_dir: Path, *, keep: int) -> None:
    if keep < 0 or not model_dir.exists():
        return
    snapshots = sorted(
        (path for path in model_dir.iterdir() if path.is_dir() and path.name.startswith("gen")),
        key=lambda path: path.name,
    )
    for old in snapshots[:-keep] if keep else snapshots:
        shutil.rmtree(old, ignore_errors=True)


def _as_tuple(value):
    if isinstance(value, list):
        return tuple(_as_tuple(item) for item in value)
    return value


def run_patternboost(
    *,
    problem: str,
    representation: str,
    local_search: str,
    surrogate: str,
    seed: int,
    iterations: int,
    population_size: int,
    elite_size: int,
    exact_every: int,
    train_every: int,
    model_samples: int,
    model_kind: str,
    model_epochs: int,
    block_size: int,
    checkpoint_every: int,
    resume: bool,
    control_mode: str,
    out_dir: str | Path,
    n: int,
    grid: int,
    run_id: str | None = None,
    stage: str = "pilot",
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    if problem not in SCORERS:
        raise ValueError("PatternBoost runner currently supports the three main ablation problems")
    if control_mode not in {"patternboost", "local_only", "model_only_weak_local", "shuffled_label"}:
        raise ValueError(f"unknown control mode: {control_mode}")
    effective_train_every = train_every
    effective_model_samples = model_samples
    effective_model_kind = model_kind
    effective_local_search = local_search
    if control_mode == "local_only":
        effective_train_every = iterations + 1
        effective_model_samples = 0
        effective_model_kind = "ngram"
    elif control_mode == "model_only_weak_local":
        effective_local_search = _weak_local_search(problem)
    out = Path(out_dir)
    cert_dir = out / "certificates"
    render_dir = out / "renderings"
    model_dir = out / "models"
    checkpoint_path = out / "checkpoint.json"
    cert_dir.mkdir(parents=True, exist_ok=True)
    render_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    event_path = out / "events.jsonl"
    rng = random.Random(seed)
    start_iso = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    best_cert: dict[str, Any] | None = None
    best_path: Path | None = None
    best_rendering_path: Path | None = None
    time_to_best: float | None = None
    generation_start = 0
    exact_calls = 0
    invalid = 0
    nontrivial_rejected = 0
    training_archive_pruned = 0
    repaired = 0
    duplicates = 0
    model_train_calls = 0
    num_model_samples = 0
    num_model_samples_valid = 0
    latest_model_kind = None
    stop_reason = "completed"
    completed_iterations = generation_start
    constraints = _nontrivial_constraints(problem, n)
    search_n_min = int(constraints["min_items"])
    search_n_max = max(max(n, search_n_min) * 3, 16, search_n_min)
    if resume and checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("schema") != "patternboost_checkpoint_v1":
            raise ValueError(f"unknown checkpoint schema in {checkpoint_path}")
        population = list(checkpoint.get("population", []))
        nontrivial_rejected_keys = set(str(item) for item in checkpoint.get("nontrivial_rejected_candidate_ids", []))
        loaded_archive = [
            (float(row["surrogate_score"]), dict(row["instance"]))
            for row in checkpoint.get("archive", [])
            if isinstance(row, dict) and "instance" in row
        ]
        archive = []
        for score, instance in loaded_archive:
            try:
                key = sha256_obj(decoded_geometry(instance))
            except Exception:
                training_archive_pruned += 1
                continue
            ok, _reason = _training_instance_ok(problem, instance, constraints)
            if key in nontrivial_rejected_keys or not ok:
                training_archive_pruned += 1
                continue
            archive.append((score, instance))
        seen = set(str(item) for item in checkpoint.get("seen", []))
        generation_start = int(checkpoint.get("next_generation", 0))
        completed_iterations = generation_start
        rng.setstate(_as_tuple(checkpoint["rng_state"]))
        exact_calls = int(checkpoint.get("num_exact_calls", 0))
        invalid = int(checkpoint.get("num_invalid_samples", 0))
        nontrivial_rejected = int(checkpoint.get("num_nontrivial_rejected", 0))
        repaired = int(checkpoint.get("num_repaired_samples", 0))
        duplicates = int(checkpoint.get("num_duplicates", 0))
        model_train_calls = int(checkpoint.get("num_model_train_calls", 0))
        num_model_samples = int(checkpoint.get("num_model_samples", 0))
        num_model_samples_valid = int(checkpoint.get("num_model_samples_valid", 0))
        training_archive_pruned += int(checkpoint.get("num_training_archive_pruned", 0))
        latest_model_kind = checkpoint.get("latest_model_kind")
        time_to_best = checkpoint.get("time_to_best")
        if checkpoint.get("best_certificate_path"):
            best_path = Path(str(checkpoint["best_certificate_path"]))
            if best_path.exists():
                best_cert = json.loads(best_path.read_text(encoding="utf-8"))
        if checkpoint.get("best_rendering_path"):
            best_rendering_path = Path(str(checkpoint["best_rendering_path"]))
    else:
        population = [
            initial_instance_for_representation(problem, representation, rng, n=search_n_min, grid=grid)
            for _ in range(population_size)
        ]
        archive: list[tuple[float, dict[str, Any]]] = []
        seen: set[str] = set()
        nontrivial_rejected_keys: set[str] = set()

    def exact_audit(instance: dict[str, Any], generation: int, source: str) -> dict[str, Any] | None:
        nonlocal best_cert, best_path, best_rendering_path, time_to_best, exact_calls, nontrivial_rejected
        clean_instance = decoded_geometry(instance)
        try:
            cert = SCORERS[problem].score_instance(clean_instance)
        except Exception:
            return None
        exact_calls += 1
        cert["candidate_id"] = sha256_obj(clean_instance)
        cert["representation"] = representation
        cert["local_search"] = local_search
        cert["surrogate"] = surrogate
        cert["source_type"] = source
        cert["control_mode"] = control_mode
        cert["generation"] = generation
        cert = attach_runtime_provenance(cert, Path.cwd())
        cert = attach_certificate_hash(cert)
        ok, reason = _nontrivial_certificate_ok(problem, cert, constraints)
        if not ok:
            nontrivial_rejected += 1
            nontrivial_rejected_keys.add(str(cert["candidate_id"]))
            cert["solver_status"] = "rejected_nontriviality"
            cert["nontriviality_rejected"] = True
            cert["nontriviality_rejected_reason"] = reason
            return cert
        if best_cert is None or float(cert["score"]) > float(best_cert["score"]):
            cert_path = cert_dir / f"best_iter{generation:06d}_{cert['certificate_hash'][:12]}.json"
            rendering_path = render_dir / f"best_iter{generation:06d}_{cert['certificate_hash'][:12]}.svg"
            write_json(cert_path, cert)
            render_certificate(cert, rendering_path)
            best_cert = cert
            best_path = cert_path
            best_rendering_path = rendering_path
            time_to_best = time.perf_counter() - start
        return cert

    def purge_archive_for_training() -> None:
        nonlocal archive, training_archive_pruned
        kept: list[tuple[float, dict[str, Any]]] = []
        for score, instance in archive:
            try:
                key = sha256_obj(decoded_geometry(instance))
            except Exception:
                training_archive_pruned += 1
                continue
            ok, _reason = _training_instance_ok(problem, instance, constraints)
            if key in nontrivial_rejected_keys or not ok:
                training_archive_pruned += 1
                continue
            kept.append((score, instance))
        archive = kept

    def make_training_texts() -> list[str]:
        purge_archive_for_training()
        top = sorted(archive, key=lambda item: item[0], reverse=True)[: max(elite_size * 8, 8)]
        if control_mode == "shuffled_label":
            top = list(archive)
            rng.shuffle(top)
            top = top[: max(elite_size * 8, 8)]
        return [instance_to_text(instance) for _, instance in top]

    def budget_exhausted() -> bool:
        return budget_seconds is not None and budget_seconds > 0 and time.perf_counter() - start >= budget_seconds

    def write_checkpoint(next_generation: int) -> None:
        purge_archive_for_training()
        write_json(
            checkpoint_path,
            {
                "schema": "patternboost_checkpoint_v1",
                "run_id": run_id,
                "problem": problem,
                "representation": representation,
                "local_search": local_search,
                "surrogate": surrogate,
                "control_mode": control_mode,
                "rng_seed": seed,
                "next_generation": next_generation,
                "iterations": iterations,
                "nontrivial_constraints": constraints,
                "search_n_min": search_n_min,
                "search_n_max": search_n_max,
                "population": population,
                "archive": [
                    {"surrogate_score": score, "instance": instance}
                    for score, instance in sorted(archive, key=lambda item: item[0], reverse=True)[: max(population_size * 8, 64)]
                    if sha256_obj(decoded_geometry(instance)) not in nontrivial_rejected_keys
                ],
                "seen": sorted(seen),
                "nontrivial_rejected_candidate_ids": sorted(nontrivial_rejected_keys),
                "rng_state": rng.getstate(),
                "best_certificate_path": None if best_path is None else str(best_path),
                "best_rendering_path": None if best_rendering_path is None else str(best_rendering_path),
                "best_certificate_hash": None if best_cert is None else best_cert.get("certificate_hash"),
                "best_exact_score": None if best_cert is None else best_cert.get("score"),
                "time_to_best": time_to_best,
                "num_exact_calls": exact_calls,
                "num_invalid_samples": invalid,
                "num_nontrivial_rejected": nontrivial_rejected,
                "num_training_archive_pruned": training_archive_pruned,
                "num_repaired_samples": repaired,
                "num_duplicates": duplicates,
                "num_model_train_calls": model_train_calls,
                "num_model_samples": num_model_samples,
                "num_model_samples_valid": num_model_samples_valid,
                "latest_model_kind": latest_model_kind,
                "stop_reason": stop_reason,
                "completed_iterations": completed_iterations,
            },
        )

    event_mode = "a" if resume and checkpoint_path.exists() else "w"
    with event_path.open(event_mode, encoding="utf-8") as events:
        if generation_start:
            events.write(json.dumps({
                "schema": "resume_event_v1",
                "time": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "checkpoint": str(checkpoint_path),
                "generation_start": generation_start,
            }, sort_keys=True) + "\n")
        for generation in range(generation_start, iterations):
            if budget_exhausted():
                stop_reason = "budget_exhausted"
                events.write(json.dumps({
                    "schema": "stop_event_v1",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "reason": stop_reason,
                    "generation": generation,
                    "elapsed_seconds": time.perf_counter() - start,
                    "budget_seconds": budget_seconds,
                }, sort_keys=True) + "\n")
                write_checkpoint(generation)
                break
            scored: list[tuple[float, dict[str, Any], dict[str, Any], str, str]] = []
            for instance in population:
                try:
                    before_geometry = decoded_geometry(instance)
                    candidate = repair_instance_for_representation(
                        problem,
                        representation,
                        instance,
                        grid=grid,
                        n_min=search_n_min,
                        n_max=search_n_max,
                    )
                except Exception:
                    invalid += 1
                    continue
                if decoded_geometry(candidate) != before_geometry:
                    repaired += 1
                source = instance.get("_source_type", candidate.get("_source_type", "initial_or_local"))
                if source:
                    candidate["_source_type"] = source
                clean_instance = decoded_geometry(candidate)
                key = sha256_obj(clean_instance)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                try:
                    row = surrogate_score(problem, surrogate, clean_instance)
                except Exception as exc:
                    invalid += 1
                    events.write(json.dumps({
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "control_mode": control_mode,
                        "generation": generation,
                        "candidate_id": key,
                        "source_type": source,
                        "exact_status": "invalid",
                        "error": repr(exc),
                    }, sort_keys=True) + "\n")
                    continue
                ok, reason = _nontrivial_surrogate_ok(problem, clean_instance, row.get("features", {}), constraints)
                if not ok:
                    nontrivial_rejected += 1
                    events.write(json.dumps({
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "representation": representation,
                        "local_search": local_search,
                        "surrogate": surrogate,
                        "control_mode": control_mode,
                        "generation": generation,
                        "candidate_id": key,
                        "source_type": source,
                        "exact_status": "rejected_nontriviality",
                        "rejected_reason": reason,
                        "surrogate_features": row.get("features", {}),
                    }, sort_keys=True) + "\n")
                    continue
                s_score = float(row["surrogate_score"])
                scored.append((s_score, candidate, row["features"], key, source))
                archive.append((s_score, candidate))
            scored.sort(key=lambda item: item[0], reverse=True)
            elites = scored[: max(1, elite_size)]

            if generation % max(1, exact_every) == 0 or generation == iterations - 1:
                for rank, (s_score, instance, features, key, source) in enumerate(elites):
                    cert = exact_audit(instance, generation, source)
                    events.write(json.dumps({
                        "schema": "candidate_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "problem": problem,
                        "representation": representation,
                        "local_search": local_search,
                        "surrogate": surrogate,
                        "control_mode": control_mode,
                        "generation": generation,
                        "rank": rank,
                        "candidate_id": key,
                        "source_type": source,
                        "surrogate_score": s_score,
                        "surrogate_features": features,
                        "exact_status": None if cert is None else cert["solver_status"],
                        "exact_score": None if cert is None else cert["score"],
                        "best_exact_score": None if best_cert is None else best_cert["score"],
                    }, sort_keys=True) + "\n")
                    if cert is not None and cert.get("nontriviality_rejected"):
                        archive = [
                            (score, archived_instance)
                            for score, archived_instance in archive
                            if sha256_obj(decoded_geometry(archived_instance)) != key
                        ]

            elites = [item for item in elites if item[3] not in nontrivial_rejected_keys]
            next_population = [instance for _, instance, _, _, _ in elites]
            if generation > 0 and generation % max(1, effective_train_every) == 0 and archive and next_population:
                texts = make_training_texts()
                if not texts:
                    events.write(json.dumps({
                        "schema": "model_event_v1",
                        "time": datetime.now(timezone.utc).isoformat(),
                        "run_id": run_id,
                        "generation": generation,
                        "model_kind": effective_model_kind,
                        "control_mode": control_mode,
                        "skipped": "no_large_training_examples",
                    }, sort_keys=True) + "\n")
                else:
                    try:
                        model = train_model(
                            texts,
                            model_kind=effective_model_kind,
                            seed=seed + generation,
                            epochs=model_epochs,
                            block_size=block_size,
                        )
                        latest_model_kind = model.model_kind
                        model_train_calls += 1
                        artifact_keep = _model_artifact_keep()
                        if artifact_keep:
                            save_model_artifacts(model, model_dir / f"gen{generation:06d}_{model.model_kind}")
                            _prune_model_artifacts(model_dir, keep=artifact_keep)
                        sampled = sample_model(model, rng, count=effective_model_samples, max_tokens=block_size * 4)
                        num_model_samples += effective_model_samples
                        for sample in sampled:
                            if not isinstance(sample, dict):
                                invalid += 1
                                continue
                            try:
                                before_geometry = decoded_geometry(sample)
                                clean_sample = repair_instance_for_representation(
                                    problem,
                                    representation,
                                    sample,
                                    grid=grid,
                                    n_min=search_n_min,
                                    n_max=search_n_max,
                                )
                            except Exception:
                                invalid += 1
                                continue
                            if decoded_geometry(clean_sample) != before_geometry:
                                repaired += 1
                            if clean_sample.get("schema") != next_population[0].get("schema"):
                                invalid += 1
                                continue
                            try:
                                sample_row = surrogate_score(problem, surrogate, decoded_geometry(clean_sample))
                            except Exception:
                                invalid += 1
                                continue
                            ok, reason = _nontrivial_surrogate_ok(
                                problem,
                                decoded_geometry(clean_sample),
                                sample_row.get("features", {}),
                                constraints,
                            )
                            if not ok:
                                nontrivial_rejected += 1
                                continue
                            clean_sample["_source_type"] = "model_sample"
                            next_population.append(clean_sample)
                            num_model_samples_valid += 1
                        events.write(json.dumps({
                            "schema": "model_event_v1",
                            "time": datetime.now(timezone.utc).isoformat(),
                            "run_id": run_id,
                            "generation": generation,
                            "model_kind": model.model_kind,
                            "num_training_texts": len(texts),
                            "num_requested_samples": effective_model_samples,
                            "num_valid_samples_total": num_model_samples_valid,
                            "control_mode": control_mode,
                        }, sort_keys=True) + "\n")
                    except Exception as exc:
                        events.write(json.dumps({
                            "schema": "model_event_v1",
                            "time": datetime.now(timezone.utc).isoformat(),
                            "run_id": run_id,
                            "generation": generation,
                            "model_kind": effective_model_kind,
                            "control_mode": control_mode,
                            "error": repr(exc),
                        }, sort_keys=True) + "\n")

            while len(next_population) < population_size:
                if not next_population:
                    fresh = initial_instance_for_representation(problem, representation, rng, n=search_n_min, grid=grid)
                    fresh["_source_type"] = "random_reseed"
                    next_population.append(fresh)
                    continue
                parent = rng.choice(next_population)
                try:
                    child = mutate_instance(
                        problem,
                        effective_local_search,
                        parent,
                        rng,
                        grid=grid,
                        n_min=search_n_min,
                        n_max=search_n_max,
                        representation=representation,
                    )
                except Exception:
                    invalid += 1
                    child = initial_instance_for_representation(problem, representation, rng, n=search_n_min, grid=grid)
                    child["_source_type"] = "random_reseed"
                    next_population.append(child)
                    continue
                child["_source_type"] = "local_mutation"
                next_population.append(child)
            population = next_population[:population_size]
            completed_iterations = generation + 1
            if (generation + 1) % max(1, checkpoint_every) == 0 or generation == iterations - 1:
                write_checkpoint(generation + 1)
        else:
            completed_iterations = iterations

    summary = {
        "schema": "run_summary_v1",
        "run_id": run_id,
        "stage": stage,
        "problem": problem,
        "representation": representation,
        "local_search": local_search,
        "surrogate": surrogate,
        "control_mode": control_mode,
        "rng_seed": seed,
        "iterations": iterations,
        "completed_iterations": completed_iterations,
        "stop_reason": stop_reason,
        "population_size": population_size,
        "elite_size": elite_size,
        "exact_every": exact_every,
        "train_every": train_every,
        "model_samples": model_samples,
        "effective_train_every": effective_train_every,
        "effective_model_samples": effective_model_samples,
        "effective_local_search": effective_local_search,
        "model_hparams": {
            "model_kind_requested": effective_model_kind,
            "model_kind_latest": latest_model_kind,
            "epochs": model_epochs,
            "block_size": block_size,
        },
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_every": checkpoint_every,
        "resumed_from_checkpoint": bool(resume and generation_start > 0),
        "n": n,
        "grid": grid,
        "search_n_min": search_n_min,
        "search_n_max": search_n_max,
        "budget_seconds": budget_seconds,
        "start_time": start_iso,
        "end_time": datetime.now(timezone.utc).isoformat(),
        "return_code": 0,
        "best_exact_score": None if best_cert is None else best_cert["score"],
        "time_to_best": time_to_best,
        "best_certificate_path": None if best_path is None else str(best_path),
        "best_rendering_path": None if best_rendering_path is None else str(best_rendering_path),
        "best_certificate_hash": None if best_cert is None else best_cert["certificate_hash"],
        "num_exact_calls": exact_calls,
        "num_exact_timeouts": 0,
        "num_invalid_samples": invalid,
        "num_nontrivial_rejected": nontrivial_rejected,
        "num_training_archive_pruned": training_archive_pruned,
        "nontrivial_constraints": constraints,
        "num_repaired_samples": repaired,
        "num_duplicates": duplicates,
        "num_model_train_calls": model_train_calls,
        "num_model_samples": num_model_samples,
        "num_model_samples_valid": num_model_samples_valid,
        "num_exports": len(list(cert_dir.glob("*.json"))),
        "event_stream": str(event_path),
        "elapsed_seconds": time.perf_counter() - start,
    }
    write_json(out / "summary.json", summary)
    return summary


def _weak_local_search(problem: str) -> str:
    return {
        "misr": "coord_anneal",
        "unit_square": "coord_mutation",
        "guillotine": "packing_resize",
    }[problem]


def _nontrivial_constraints(problem: str, requested_n: int) -> dict[str, Any]:
    base = max(2, int(requested_n))
    large = LARGE_EXAMPLE_CONSTRAINTS.get(problem, {})
    if problem == "misr":
        return {
            "min_items": max(int(large["min_items"]), base),
        }
    if problem == "unit_square":
        return {
            "min_items": max(int(large["min_items"]), base),
            "min_tau_int": int(large["min_tau_int"]),
        }
    if problem == "guillotine":
        return {
            "min_items": max(int(large["min_items"]), base),
            "min_destroyed": int(large["min_destroyed"]),
        }
    return {"min_items": base}


def _instance_item_count(problem: str, instance: dict[str, Any]) -> int:
    if problem == "misr":
        return len(instance.get("rectangles") or [])
    if problem == "unit_square":
        return len(instance.get("squares") or [])
    if problem == "guillotine":
        return len(instance.get("rectangles") or [])
    return 0


def _training_instance_ok(
    problem: str,
    instance: dict[str, Any],
    constraints: dict[str, Any],
) -> tuple[bool, str | None]:
    try:
        clean_instance = decoded_geometry(instance)
    except Exception:
        return False, "invalid_geometry"
    min_items = int(constraints.get("min_items", 2))
    n_items = _instance_item_count(problem, clean_instance)
    if n_items < min_items:
        return False, f"training_item_count_below_{min_items}"
    return True, None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nontrivial_surrogate_ok(
    problem: str,
    instance: dict[str, Any],
    features: dict[str, Any],
    constraints: dict[str, Any],
) -> tuple[bool, str | None]:
    min_items = int(constraints.get("min_items", 2))
    n_items = _instance_item_count(problem, instance)
    if n_items < min_items:
        return False, f"item_count_below_{min_items}"

    if problem == "unit_square":
        min_tau = int(constraints.get("min_tau_int", 0))
        tau_hint = _as_int(features.get("tau_int"))
        if tau_hint is None:
            tau_hint = _as_int(features.get("greedy_cover"))
        if tau_hint is not None and tau_hint < min_tau:
            return False, f"stabbing_integer_cover_below_{min_tau}"

    return True, None


def _nontrivial_certificate_ok(
    problem: str,
    cert: dict[str, Any],
    constraints: dict[str, Any],
) -> tuple[bool, str | None]:
    min_items = int(constraints.get("min_items", 2))
    if problem == "unit_square":
        n_items = len(cert.get("squares") or [])
        if n_items < min_items:
            return False, f"item_count_below_{min_items}"
        tau_int = _as_int(cert.get("tau_int"))
        min_tau = int(constraints.get("min_tau_int", 0))
        if tau_int is not None and tau_int < min_tau:
            return False, f"stabbing_integer_cover_below_{min_tau}"
    elif problem == "guillotine":
        n_items = _as_int(cert.get("n"))
        if n_items is None:
            n_items = len(cert.get("rectangles") or [])
        if n_items < min_items:
            return False, f"item_count_below_{min_items}"
        destroyed = _as_int(cert.get("destroyed"))
        min_destroyed = int(constraints.get("min_destroyed", 0))
        if destroyed is not None and destroyed < min_destroyed:
            return False, f"destroyed_below_{min_destroyed}"
    else:
        # MISR certificates use rectangles; the size gate is enough here.
        n_items = len(cert.get("rectangles") or [])
        if n_items < min_items:
            return False, f"item_count_below_{min_items}"
    return True, None
