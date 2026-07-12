#!/usr/bin/env python3
"""Compact PatternBoost matrix event streams into analysis-ready tables.

The raw event logs are intentionally verbose.  This script preserves the
information needed for learning-curve and plateau analysis without copying
every rejected or duplicate candidate into the report repository.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROBLEMS = ("misr", "unit_square", "guillotine")
EPS = 1e-12
CERTIFICATE_SCHEMAS = {
    "misr": "misr_certificate_v1",
    "unit_square": "unit_square_stab_certificate_v1",
    "guillotine": "guillotine_certificate_v1",
}
CERTIFICATE_SCORE_TOLERANCE = 1e-9


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"could not read certificate JSON: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"malformed certificate JSON at line {exc.lineno} column {exc.colno}"
    if not isinstance(value, dict):
        return None, "certificate JSON top-level value is not an object"
    return value, ""


def _load_json(path: Path) -> dict[str, Any] | None:
    value, _error = _load_json_object(path)
    return value


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def _first(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if mapping.get(key) is not None:
            return mapping[key]
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _certificate_content_hash(cert: dict[str, Any]) -> str:
    payload = dict(cert)
    payload.pop("certificate_hash", None)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _scores_match(left: Any, right: Any) -> bool:
    left_number = _as_float(left)
    right_number = _as_float(right)
    return (
        left_number is not None
        and right_number is not None
        and abs(left_number - right_number) <= CERTIFICATE_SCORE_TOLERANCE
    )


def _certificate_validation(
    cert: dict[str, Any] | None,
    *,
    parse_error: str,
    problem: str,
    expected_score: Any,
    state_hashes: Iterable[Any],
    state_scores: Iterable[Any],
) -> dict[str, Any]:
    errors: list[str] = []
    json_valid = cert is not None
    schema_valid = False
    hash_valid = False
    score_valid = False

    if cert is None:
        errors.append(parse_error or "certificate JSON is missing")
    else:
        expected_schema = CERTIFICATE_SCHEMAS[problem]
        schema = cert.get("schema")
        certificate_problem = cert.get("problem")
        schema_valid = schema == expected_schema and certificate_problem == problem
        if schema != expected_schema:
            errors.append(f"certificate schema {schema!r} does not match {expected_schema!r}")
        if certificate_problem != problem:
            errors.append(
                f"certificate problem {certificate_problem!r} does not match {problem!r}"
            )

        stored_hash = cert.get("certificate_hash")
        if not isinstance(stored_hash, str) or not stored_hash:
            errors.append("certificate hash is missing")
        elif _certificate_content_hash(cert) != stored_hash:
            errors.append("certificate hash does not match certificate content")
        else:
            conflicting_hashes = [
                value for value in state_hashes if value not in (None, "", stored_hash)
            ]
            if conflicting_hashes:
                errors.append("certificate hash does not match summary/checkpoint hash")
            else:
                hash_valid = True

        certificate_score = _as_float(cert.get("score"))
        if certificate_score is None:
            errors.append("certificate score is missing or non-finite")
        else:
            comparison_scores = [expected_score, *state_scores]
            conflicting_scores = [
                value
                for value in comparison_scores
                if value not in (None, "") and not _scores_match(certificate_score, value)
            ]
            if conflicting_scores:
                errors.append("certificate score does not match row/summary/checkpoint score")
            else:
                score_valid = True

    return {
        "certificate_json_valid": json_valid,
        "certificate_schema_valid": schema_valid,
        "certificate_hash_valid": hash_valid,
        "certificate_score_valid": score_valid,
        "certificate_valid": json_valid and schema_valid and hash_valid and score_valid,
        "certificate_validation_error": "; ".join(errors),
    }


def _git_commit(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _row_components(event_path: Path) -> tuple[str, str, str, str]:
    parts = event_path.parts
    for problem in PROBLEMS:
        if problem not in parts:
            continue
        idx = len(parts) - 1 - tuple(reversed(parts)).index(problem)
        tail = parts[idx : idx + 4]
        if len(tail) == 4:
            return tail[0], tail[1], tail[2], tail[3]
    raise ValueError(f"cannot infer matrix components from {event_path}")


def _resolve_artifact(path_value: Any, *, row_dir: Path, project_root: Path) -> Path | None:
    if not isinstance(path_value, str) or not path_value:
        return None
    path = Path(path_value)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(project_root / path)
    # Archived runs often retain the original absolute HPC path in summary.json.
    # Resolve the copied winning artifact by basename when the archive is local.
    candidates.extend(
        (
            row_dir / path.name,
            row_dir / "certificates" / path.name,
            row_dir / "renderings" / path.name,
        )
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


@dataclass
class Improvement:
    generation: int
    elapsed_seconds: float | None
    model_train_calls: int
    cumulative_model_epochs: int
    best_score: float
    exact_score: float | None
    source_type: str
    candidate_id: str
    point_kind: str = "improvement"


@dataclass
class RowData:
    problem: str
    representation: str
    local_search: str
    surrogate: str
    row_dir: Path
    event_path: Path
    summary: dict[str, Any]
    checkpoint: dict[str, Any]
    model_epochs_per_call: int
    run_id: str = ""
    start_time: datetime | None = None
    first_event_time: datetime | None = None
    last_event_time: datetime | None = None
    last_generation: int = 0
    current_model_calls: int = 0
    event_counts: Counter[str] = field(default_factory=Counter)
    source_counts: Counter[str] = field(default_factory=Counter)
    improvement_source_counts: Counter[str] = field(default_factory=Counter)
    exact_event_count: int = 0
    rejected_event_count: int = 0
    invalid_event_count: int = 0
    model_event_errors: int = 0
    model_event_skips: int = 0
    improvements: list[Improvement] = field(default_factory=list)

    @property
    def config_id(self) -> str:
        return "/".join((self.problem, self.representation, self.local_search, self.surrogate))

    def relative_seconds(self, event_time: datetime | None) -> float | None:
        return _seconds_between(self.start_time or self.first_event_time, event_time)

    def record_best(
        self,
        *,
        generation: Any,
        event_time: datetime | None,
        best_score: Any,
        exact_score: Any,
        source_type: Any,
        candidate_id: Any,
        point_kind: str = "improvement",
    ) -> None:
        score = _as_float(best_score)
        if score is None:
            return
        previous = self.improvements[-1].best_score if self.improvements else None
        if previous is not None and score <= previous + EPS:
            return
        source = str(source_type or "unknown")
        self.improvements.append(
            Improvement(
                generation=max(0, _as_int(generation) or 0),
                elapsed_seconds=self.relative_seconds(event_time),
                model_train_calls=self.current_model_calls,
                cumulative_model_epochs=self.current_model_calls * self.model_epochs_per_call,
                best_score=score,
                exact_score=_as_float(exact_score),
                source_type=source,
                candidate_id=str(candidate_id or ""),
                point_kind=point_kind,
            )
        )
        self.improvement_source_counts[source] += 1


def _load_row(event_path: Path, *, project_root: Path, default_model_epochs: int) -> RowData:
    problem, representation, local_search, surrogate = _row_components(event_path)
    row_dir = event_path.parent
    summary = _load_json(row_dir / "summary.json") or {}
    checkpoint = _load_json(row_dir / "checkpoint.json") or {}
    model_hparams = summary.get("model_hparams") if isinstance(summary.get("model_hparams"), dict) else {}
    epochs = _as_int(model_hparams.get("epochs")) or default_model_epochs
    row = RowData(
        problem=problem,
        representation=representation,
        local_search=local_search,
        surrogate=surrogate,
        row_dir=row_dir,
        event_path=event_path,
        summary=summary,
        checkpoint=checkpoint,
        model_epochs_per_call=max(0, epochs),
        run_id=str(summary.get("run_id") or checkpoint.get("run_id") or ""),
        start_time=_parse_time(summary.get("start_time")),
    )

    with event_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                row.event_counts["malformed_json"] += 1
                continue
            if not isinstance(event, dict):
                row.event_counts["non_object"] += 1
                continue
            schema = str(event.get("schema") or "unknown")
            row.event_counts[schema] += 1
            event_time = _parse_time(event.get("time"))
            if event_time is not None:
                row.first_event_time = row.first_event_time or event_time
                row.last_event_time = event_time
            generation = _as_int(event.get("generation"))
            if generation is not None:
                row.last_generation = max(row.last_generation, generation)

            if schema == "model_event_v1":
                if event.get("error"):
                    row.model_event_errors += 1
                elif event.get("skipped"):
                    row.model_event_skips += 1
                else:
                    row.current_model_calls += 1
                continue

            if schema == "candidate_event_v1":
                source = str(event.get("source_type") or "unknown")
                row.source_counts[source] += 1
                status = str(event.get("exact_status") or "")
                if status == "rejected_nontriviality" or event.get("rejected_reason"):
                    row.rejected_event_count += 1
                if status == "invalid" or event.get("error"):
                    row.invalid_event_count += 1
                if _as_float(event.get("exact_score")) is not None:
                    row.exact_event_count += 1
                row.record_best(
                    generation=event.get("generation"),
                    event_time=event_time,
                    best_score=event.get("best_exact_score"),
                    exact_score=event.get("exact_score"),
                    source_type=source,
                    candidate_id=event.get("candidate_id"),
                )
                continue

            if schema == "fallback_floor_event_v1":
                row.record_best(
                    generation=event.get("generation"),
                    event_time=event_time,
                    best_score=event.get("best_exact_score"),
                    exact_score=event.get("exact_score"),
                    source_type=event.get("source_type"),
                    candidate_id="",
                    point_kind="fallback_improvement",
                )

    return row


def _certificate_fields(cert: dict[str, Any], problem: str) -> dict[str, Any]:
    rectangles = cert.get("rectangles") if isinstance(cert.get("rectangles"), list) else []
    squares = cert.get("squares") if isinstance(cert.get("squares"), list) else []
    result: dict[str, Any] = {
        "certificate_schema": cert.get("schema", ""),
        "certificate_solver_status": cert.get("solver_status", ""),
        "certificate_score": _as_float(cert.get("score")),
        "certificate_hash": cert.get("certificate_hash", ""),
        "n_items": len(rectangles) if rectangles else len(squares),
    }
    if problem == "misr":
        result.update(
            {
                "objective_integer": _first(cert, ("alpha_int", "integral_optimum", "integer_optimum", "alpha")),
                "objective_fractional": _first(cert, ("alpha_lp", "fractional_optimum", "lp_optimum", "alpha_star")),
                "saved": "",
                "destroyed": "",
            }
        )
    elif problem == "unit_square":
        result.update(
            {
                "objective_integer": _first(cert, ("tau_int", "integer_optimum", "tau")),
                "objective_fractional": _first(cert, ("tau_lp", "fractional_optimum", "lp_optimum", "tau_star")),
                "saved": "",
                "destroyed": "",
            }
        )
    else:
        result.update(
            {
                "objective_integer": "",
                "objective_fractional": "",
                "saved": _first(cert, ("saved", "max_saved", "save")),
                "destroyed": _first(cert, ("destroyed", "min_destroyed")),
            }
        )
    return result


def _metric_row(row: RowData, *, project_root: Path) -> dict[str, Any]:
    state = row.summary or row.checkpoint
    completed = _as_int(_first(state, ("completed_iterations", "next_generation")))
    completed = max(row.last_generation, completed or 0)
    elapsed = _as_float(row.summary.get("elapsed_seconds"))
    if elapsed is None:
        elapsed = row.relative_seconds(row.last_event_time)
    summary_score = _as_float(_first(state, ("best_exact_score", "score")))
    event_score = row.improvements[-1].best_score if row.improvements else None
    best_score = max(value for value in (summary_score, event_score) if value is not None) if any(
        value is not None for value in (summary_score, event_score)
    ) else None

    total_model_calls = _as_int(state.get("num_model_train_calls"))
    if total_model_calls is None:
        total_model_calls = row.current_model_calls
    total_model_epochs = total_model_calls * row.model_epochs_per_call

    if best_score is not None and (not row.improvements or best_score > row.improvements[-1].best_score + EPS):
        row.current_model_calls = total_model_calls
        row.record_best(
            generation=completed,
            event_time=row.last_event_time,
            best_score=best_score,
            exact_score=best_score,
            source_type="summary_or_checkpoint",
            candidate_id=state.get("best_certificate_hash"),
            point_kind="recovered_final",
        )

    first_improvement = row.improvements[0] if row.improvements else None
    last_improvement = row.improvements[-1] if row.improvements else None
    best_generation = last_improvement.generation if last_improvement else None
    time_to_best = _as_float(state.get("time_to_best"))
    if time_to_best is None and last_improvement is not None:
        time_to_best = last_improvement.elapsed_seconds
    best_epoch = last_improvement.cumulative_model_epochs if last_improvement else None

    cert_path = _resolve_artifact(
        state.get("best_certificate_path"), row_dir=row.row_dir, project_root=project_root
    )
    cert: dict[str, Any] | None = None
    certificate_parse_error = "certificate path did not resolve"
    if cert_path is not None:
        cert, certificate_parse_error = _load_json_object(cert_path)
    cert_fields = _certificate_fields(cert or {}, row.problem)
    certificate_validation = _certificate_validation(
        cert,
        parse_error=certificate_parse_error,
        problem=row.problem,
        expected_score=best_score,
        state_hashes=(
            row.summary.get("best_certificate_hash"),
            row.checkpoint.get("best_certificate_hash"),
        ),
        state_scores=(
            _first(row.summary, ("best_exact_score", "score")),
            _first(row.checkpoint, ("best_exact_score", "score")),
        ),
    )
    if not cert_fields.get("n_items"):
        cert_fields["n_items"] = ""

    plateau_generations = None if best_generation is None else max(0, completed - best_generation)
    plateau_fraction = None
    if plateau_generations is not None and completed > 0:
        plateau_fraction = plateau_generations / completed
    plateau_seconds = None
    if elapsed is not None and time_to_best is not None:
        plateau_seconds = max(0.0, elapsed - time_to_best)

    source_of_best = last_improvement.source_type if last_improvement else ""
    generation_rate = completed / (elapsed / 3600.0) if elapsed and elapsed > 0 else None
    exact_calls = _as_int(state.get("num_exact_calls")) or row.exact_event_count
    exact_rate = exact_calls / (elapsed / 3600.0) if elapsed and elapsed > 0 else None
    requested_model_samples = _as_int(state.get("num_model_samples")) or 0
    valid_model_samples = _as_int(state.get("num_model_samples_valid")) or 0
    valid_model_fraction = (
        valid_model_samples / requested_model_samples if requested_model_samples > 0 else None
    )
    population_size = _as_int(state.get("population_size")) or 0
    candidate_slots = completed * population_size
    duplicate_samples = _as_int(state.get("num_duplicates")) or 0
    repaired_samples = _as_int(state.get("num_repaired_samples")) or 0
    invalid_samples = _as_int(state.get("num_invalid_samples")) or 0
    nontrivial_rejected = _as_int(state.get("num_nontrivial_rejected")) or 0
    archive_pruned = _as_int(state.get("num_training_archive_pruned")) or 0

    result = {
        "config_id": row.config_id,
        "problem": row.problem,
        "representation": row.representation,
        "local_search": row.local_search,
        "surrogate": row.surrogate,
        "run_id": row.run_id,
        "summary_present": bool(row.summary),
        "checkpoint_present": bool(row.checkpoint),
        "stop_reason": state.get("stop_reason", ""),
        "return_code": state.get("return_code", ""),
        "completed_iterations": completed,
        "elapsed_seconds": elapsed,
        "generation_rate_per_hour": generation_rate,
        "event_rows": sum(row.event_counts.values()),
        "population_size": population_size,
        "candidate_slots": candidate_slots,
        "candidate_events": row.event_counts.get("candidate_event_v1", 0),
        "exact_events": row.exact_event_count,
        "exact_calls": exact_calls,
        "exact_calls_per_hour": exact_rate,
        "rejected_events": row.rejected_event_count,
        "invalid_events": row.invalid_event_count,
        "invalid_samples": invalid_samples,
        "nontrivial_rejected_samples": nontrivial_rejected,
        "training_archive_pruned": archive_pruned,
        "repaired_samples": repaired_samples,
        "duplicate_samples": duplicate_samples,
        "duplicates_per_generation": duplicate_samples / completed if completed > 0 else None,
        "duplicate_slot_fraction": duplicate_samples / candidate_slots if candidate_slots > 0 else None,
        "repairs_per_generation": repaired_samples / completed if completed > 0 else None,
        "malformed_event_rows": row.event_counts.get("malformed_json", 0),
        "model_train_calls": total_model_calls,
        "model_epochs_per_call": row.model_epochs_per_call,
        "total_model_epochs": total_model_epochs,
        "model_event_errors": row.model_event_errors,
        "model_event_skips": row.model_event_skips,
        "model_samples_requested": requested_model_samples,
        "model_samples_valid": valid_model_samples,
        "model_samples_valid_fraction": valid_model_fraction,
        "initial_best_score": first_improvement.best_score if first_improvement else None,
        "best_score": best_score,
        "score_gain": (
            best_score - first_improvement.best_score
            if best_score is not None and first_improvement is not None
            else None
        ),
        "improvement_count": len(row.improvements),
        "best_generation": best_generation,
        "best_model_epoch": best_epoch,
        "time_to_best_seconds": time_to_best,
        "plateau_generations": plateau_generations,
        "plateau_fraction": plateau_fraction,
        "plateau_seconds": plateau_seconds,
        "source_of_best": source_of_best,
        "fallback_floor_used": bool(state.get("fallback_floor_used", False)),
        "best_certificate_path": str(cert_path) if cert_path is not None else "",
        "best_rendering_path": state.get("best_rendering_path", ""),
        "summary_event_score_difference": (
            summary_score - event_score
            if summary_score is not None and event_score is not None
            else None
        ),
        "source_event_counts_json": json.dumps(dict(sorted(row.source_counts.items())), sort_keys=True),
        "improvement_source_counts_json": json.dumps(
            dict(sorted(row.improvement_source_counts.items())), sort_keys=True
        ),
    }
    result.update(cert_fields)
    result.update(certificate_validation)
    return result


def _step_score(improvements: list[Improvement], *, axis: str, target: float) -> float | None:
    # Align normalized curves at the first exact-audited candidate.  Some rows
    # do not emit that event until after their first model-training call; using
    # a missing value before then would make aggregate quantiles use a changing
    # subset of configurations and could create an artificial downward step.
    value = improvements[0].best_score if improvements else None
    for point in improvements:
        coordinate = {
            "generation": float(point.generation),
            "elapsed_seconds": point.elapsed_seconds,
            "model_epoch": float(point.cumulative_model_epochs),
        }[axis]
        if coordinate is None:
            continue
        if coordinate <= target + EPS:
            value = point.best_score
        else:
            break
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not names:
            return
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in names})


def _batch_expectation_issues(
    rows: list[RowData],
    *,
    expected_rows: int,
    expected_problem_counts: dict[str, int] | None,
    expected_configs: Iterable[str] | None,
) -> tuple[list[str], dict[str, int], set[str] | None]:
    issues: list[str] = []
    actual_problems = Counter(row.problem for row in rows)
    actual_configs = {row.config_id for row in rows}
    expected_config_values = list(expected_configs) if expected_configs is not None else None
    expected_config_set = (
        set(expected_config_values) if expected_config_values is not None else None
    )

    if expected_config_values is not None:
        duplicate_expected_configs = sorted(
            config
            for config, count in Counter(expected_config_values).items()
            if count > 1
        )
        if duplicate_expected_configs:
            issues.append(
                f"duplicate expected configuration identifiers: {duplicate_expected_configs}"
            )

    normalized_problem_counts: dict[str, int] = {}
    if expected_problem_counts is not None:
        unknown_problems = sorted(set(expected_problem_counts) - set(PROBLEMS))
        if unknown_problems:
            issues.append(f"unknown expected problems: {unknown_problems}")
        normalized_problem_counts = {
            problem: int(expected_problem_counts.get(problem, 0)) for problem in PROBLEMS
        }
        invalid_counts = {
            problem: count for problem, count in normalized_problem_counts.items() if count < 0
        }
        if invalid_counts:
            issues.append(f"negative expected problem counts: {invalid_counts}")
        if sum(normalized_problem_counts.values()) != expected_rows:
            issues.append(
                "expected problem counts sum to "
                f"{sum(normalized_problem_counts.values())}, not expected_rows={expected_rows}"
            )

    config_problem_counts: dict[str, int] = {}
    if expected_config_set is not None:
        invalid_configs = sorted(
            config
            for config in expected_config_set
            if config.split("/", 1)[0] not in PROBLEMS or config.count("/") != 3
        )
        if invalid_configs:
            issues.append(f"invalid expected configuration identifiers: {invalid_configs}")
        config_problem_counts = dict(
            Counter(config.split("/", 1)[0] for config in expected_config_set)
        )
        if len(expected_config_set) != expected_rows:
            issues.append(
                f"expected configuration set has {len(expected_config_set)} rows, "
                f"not expected_rows={expected_rows}"
            )
        missing = sorted(expected_config_set - actual_configs)
        unexpected = sorted(actual_configs - expected_config_set)
        if missing:
            issues.append(f"missing expected configurations: {missing}")
        if unexpected:
            issues.append(f"unexpected configurations: {unexpected}")
        if normalized_problem_counts and any(
            normalized_problem_counts[problem] != config_problem_counts.get(problem, 0)
            for problem in PROBLEMS
        ):
            issues.append(
                "expected configuration set problem counts do not match explicit expected problem counts"
            )

    effective_problem_counts = normalized_problem_counts
    if not effective_problem_counts and expected_config_set is not None:
        effective_problem_counts = {
            problem: config_problem_counts.get(problem, 0) for problem in PROBLEMS
        }
    if not effective_problem_counts and expected_rows == 81:
        effective_problem_counts = {problem: 27 for problem in PROBLEMS}

    for problem, expected_count in effective_problem_counts.items():
        actual_count = actual_problems.get(problem, 0)
        if actual_count != expected_count:
            issues.append(f"{problem}: expected {expected_count} rows, found {actual_count}")

    return issues, effective_problem_counts, expected_config_set


def _parse_problem_count(value: str) -> tuple[str, int]:
    problem, separator, raw_count = value.partition("=")
    if not separator or problem not in PROBLEMS:
        choices = ", ".join(PROBLEMS)
        raise argparse.ArgumentTypeError(f"expected PROBLEM=COUNT where PROBLEM is one of: {choices}")
    try:
        count = int(raw_count)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid count in {value!r}") from exc
    if count < 0:
        raise argparse.ArgumentTypeError(f"count must be non-negative in {value!r}")
    return problem, count


def compact_run(
    root: Path,
    out_dir: Path,
    *,
    expected_rows: int,
    default_model_epochs: int,
    strict: bool,
    completed_only: bool = False,
    expected_problem_counts: dict[str, int] | None = None,
    expected_configs: Iterable[str] | None = None,
) -> dict[str, Any]:
    project_root = Path.cwd().resolve()
    all_event_paths = sorted(root.rglob("events.jsonl"))
    main_event_paths = [path for path in all_event_paths if "main" in path.parts]
    event_paths = main_event_paths or all_event_paths
    if completed_only:
        event_paths = [path for path in event_paths if (path.parent / "summary.json").exists()]
    rows = [
        _load_row(path, project_root=project_root, default_model_epochs=default_model_epochs)
        for path in event_paths
    ]
    metrics = [_metric_row(row, project_root=project_root) for row in rows]

    improvement_rows: list[dict[str, Any]] = []
    normalized_rows: list[dict[str, Any]] = []
    for row, metric in zip(rows, metrics):
        total_generation = float(metric["completed_iterations"] or 0)
        total_elapsed = _as_float(metric["elapsed_seconds"]) or 0.0
        total_epochs = float(metric["total_model_epochs"] or 0)
        for index, point in enumerate(row.improvements, start=1):
            improvement_rows.append(
                {
                    "config_id": row.config_id,
                    "problem": row.problem,
                    "representation": row.representation,
                    "local_search": row.local_search,
                    "surrogate": row.surrogate,
                    "improvement_index": index,
                    "point_kind": point.point_kind,
                    "generation": point.generation,
                    "generation_fraction": point.generation / total_generation if total_generation > 0 else "",
                    "elapsed_seconds": point.elapsed_seconds,
                    "elapsed_fraction": (
                        point.elapsed_seconds / total_elapsed
                        if point.elapsed_seconds is not None and total_elapsed > 0
                        else ""
                    ),
                    "model_train_calls": point.model_train_calls,
                    "cumulative_model_epochs": point.cumulative_model_epochs,
                    "model_epoch_fraction": (
                        point.cumulative_model_epochs / total_epochs if total_epochs > 0 else ""
                    ),
                    "best_score": point.best_score,
                    "exact_score": point.exact_score,
                    "source_type": point.source_type,
                    "candidate_id": point.candidate_id,
                }
            )

        for axis, total in (
            ("generation", total_generation),
            ("elapsed_seconds", total_elapsed),
            ("model_epoch", total_epochs),
        ):
            for percent in range(101):
                target = total * percent / 100.0
                score = _step_score(row.improvements, axis=axis, target=target)
                normalized_rows.append(
                    {
                        "config_id": row.config_id,
                        "problem": row.problem,
                        "representation": row.representation,
                        "local_search": row.local_search,
                        "surrogate": row.surrogate,
                        "axis": axis,
                        "progress_percent": percent,
                        "axis_value": target,
                        "best_score": score,
                    }
                )

    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "row_metrics.csv"
    improvements_path = out_dir / "score_improvements.csv"
    normalized_path = out_dir / "normalized_learning_curves.csv"
    _write_csv(metrics_path, metrics)
    _write_csv(improvements_path, improvement_rows)
    _write_csv(normalized_path, normalized_rows)

    problems = Counter(row.problem for row in rows)
    configs = Counter(row.config_id for row in rows)
    issues: list[str] = []
    if len(rows) != expected_rows:
        issues.append(f"expected {expected_rows} rows, found {len(rows)}")
    duplicates = sorted(config for config, count in configs.items() if count != 1)
    if duplicates:
        issues.append(f"non-unique configurations: {duplicates}")
    batch_issues, effective_problem_counts, expected_config_set = _batch_expectation_issues(
        rows,
        expected_rows=expected_rows,
        expected_problem_counts=expected_problem_counts,
        expected_configs=expected_configs,
    )
    issues.extend(batch_issues)
    for metric in metrics:
        config = metric["config_id"]
        if not metric["summary_present"]:
            issues.append(f"{config}: missing summary.json")
        if metric["best_score"] in (None, ""):
            issues.append(f"{config}: missing best score")
        if not metric["best_certificate_path"]:
            issues.append(f"{config}: missing best certificate")
        elif not metric["certificate_valid"]:
            issues.append(
                f"{config}: invalid best certificate: {metric['certificate_validation_error']}"
            )
        difference = _as_float(metric["summary_event_score_difference"])
        if difference is not None and abs(difference) > 1e-9:
            issues.append(f"{config}: summary/event score mismatch {difference}")
        if metric["malformed_event_rows"]:
            issues.append(f"{config}: malformed event rows {metric['malformed_event_rows']}")

    manifest = {
        "schema": "patternboost_matrix_analysis_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root.resolve()),
        "analysis_git_commit": _git_commit(project_root),
        "analysis_script": str(Path(__file__).resolve()),
        "analysis_script_sha256": _sha256(Path(__file__).resolve()),
        "expected_rows": expected_rows,
        "expected_problem_counts": dict(sorted(effective_problem_counts.items())),
        "expected_config_count": (
            len(expected_config_set) if expected_config_set is not None else None
        ),
        "rows_found": len(rows),
        "problem_counts": dict(sorted(problems.items())),
        "source_run_ids": sorted(row.run_id for row in rows if row.run_id),
        "source_git_commit_prefixes": sorted(
            {
                row.run_id.rsplit("/git", 1)[1]
                for row in rows
                if "/git" in row.run_id
            }
        ),
        "summary_count": sum(bool(metric["summary_present"]) for metric in metrics),
        "resolved_certificate_count": sum(
            bool(metric["best_certificate_path"]) for metric in metrics
        ),
        "certificate_count": sum(bool(metric["certificate_valid"]) for metric in metrics),
        "event_rows": sum(int(metric["event_rows"]) for metric in metrics),
        "exact_events": sum(int(metric["exact_events"]) for metric in metrics),
        "model_train_calls": sum(int(metric["model_train_calls"]) for metric in metrics),
        "issues": issues,
        "outputs": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (metrics_path, improvements_path, normalized_path)
        },
    }
    manifest_path = out_dir / "analysis_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if strict and issues:
        raise SystemExit("strict compaction failed:\n- " + "\n- ".join(issues))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compact a PatternBoost matrix event stream for trajectory analysis."
    )
    parser.add_argument("root", type=Path, help="main_results directory containing the main/ tree")
    parser.add_argument("--out-dir", type=Path, required=True, help="directory for compact CSV/JSON outputs")
    parser.add_argument(
        "--expected-rows",
        type=int,
        help="expected total rows (defaults to 81, or to the supplied counts/configuration set)",
    )
    parser.add_argument(
        "--expected-problem-count",
        action="append",
        default=[],
        metavar="PROBLEM=COUNT",
        type=_parse_problem_count,
        help="expected rows for one problem; repeat for problem-specific partial batches",
    )
    parser.add_argument(
        "--expected-config",
        action="append",
        default=[],
        metavar="CONFIG_ID",
        help="expected problem/representation/local_search/surrogate ID; repeat for each row",
    )
    parser.add_argument("--default-model-epochs", type=int, default=3)
    parser.add_argument("--strict", action="store_true", help="fail on missing rows, summaries, scores, or certificates")
    parser.add_argument(
        "--completed-only",
        action="store_true",
        help="ignore interrupted event streams that do not have a summary.json",
    )
    args = parser.parse_args()

    expected_problem_counts: dict[str, int] | None = None
    if args.expected_problem_count:
        repeated_problems = sorted(
            problem
            for problem, count in Counter(
                problem for problem, _count in args.expected_problem_count
            ).items()
            if count > 1
        )
        if repeated_problems:
            parser.error(
                "--expected-problem-count was repeated for: " + ", ".join(repeated_problems)
            )
        expected_problem_counts = dict(args.expected_problem_count)

    expected_configs = args.expected_config or None
    if expected_configs and len(set(expected_configs)) != len(expected_configs):
        parser.error("--expected-config values must be unique")

    if args.expected_rows is not None:
        expected_rows = args.expected_rows
    elif expected_problem_counts is not None:
        expected_rows = sum(expected_problem_counts.values())
    elif expected_configs is not None:
        expected_rows = len(expected_configs)
    else:
        expected_rows = 81
    if expected_rows < 0:
        parser.error("--expected-rows must be non-negative")

    manifest = compact_run(
        args.root,
        args.out_dir,
        expected_rows=expected_rows,
        default_model_epochs=args.default_model_epochs,
        strict=args.strict,
        completed_only=args.completed_only,
        expected_problem_counts=expected_problem_counts,
        expected_configs=expected_configs,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
