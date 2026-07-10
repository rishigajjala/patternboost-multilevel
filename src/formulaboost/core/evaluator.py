from __future__ import annotations

import time
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from formulaboost.core.domain import Domain
from formulaboost.core.family import FamilyProgram


@dataclass
class CandidateFamilyResult:
    program_id: str
    domain: str
    train_scores: list[float]
    val_scores: list[float]
    test_scores: list[float]
    invalid_count: int
    mean_runtime_sec: float
    complexity: int
    novelty: float
    notes: str = ""
    evaluations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def train_mean_score(self) -> float:
        return mean(self.train_scores) if self.train_scores else 0.0

    @property
    def val_mean_score(self) -> float:
        return mean(self.val_scores) if self.val_scores else 0.0

    @property
    def test_mean_score(self) -> float:
        return mean(self.test_scores) if self.test_scores else 0.0

    @property
    def invalid_rate(self) -> float:
        total = len(self.evaluations)
        return 0.0 if total == 0 else self.invalid_count / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "domain": self.domain,
            "train_mean_score": self.train_mean_score,
            "val_mean_score": self.val_mean_score,
            "test_mean_score": self.test_mean_score,
            "train_scores": self.train_scores,
            "val_scores": self.val_scores,
            "test_scores": self.test_scores,
            "invalid_count": self.invalid_count,
            "invalid_rate": self.invalid_rate,
            "mean_runtime_sec": self.mean_runtime_sec,
            "complexity": self.complexity,
            "novelty": self.novelty,
            "notes": self.notes,
            "evaluations": self.evaluations,
        }


class FamilyEvaluator:
    def evaluate(
        self,
        program: FamilyProgram,
        domain: Domain,
        train_params: list[dict[str, Any]],
        val_params: list[dict[str, Any]],
        test_params: list[dict[str, Any]],
    ) -> CandidateFamilyResult:
        evaluations: list[dict[str, Any]] = []
        invalid_count = 0
        runtimes: list[float] = []
        split_scores = {"train": [], "val": [], "test": []}

        for split, params_list in (
            ("train", train_params),
            ("val", val_params),
            ("test", test_params),
        ):
            for params in params_list:
                started = time.perf_counter()
                try:
                    obj = program.evaluate(params)
                    runtime = time.perf_counter() - started
                    valid = domain.validate(obj)
                    raw_score = domain.score(obj)
                    normalized_score = domain.normalize_score(raw_score, params) if valid else -10.0
                    canonical = domain.canonicalize(obj) if valid else obj.canonical
                    object_data = obj.data
                    error = None
                except Exception as exc:  # pragma: no cover - exercised by CLI failures
                    runtime = time.perf_counter() - started
                    valid = False
                    raw_score = -10.0
                    normalized_score = -10.0
                    canonical = None
                    object_data = {}
                    error = str(exc)

                runtimes.append(runtime)
                if not valid:
                    invalid_count += 1
                split_scores[split].append(float(normalized_score))
                evaluations.append(
                    {
                        "split": split,
                        "params": params,
                        "valid": valid,
                        "raw_score": raw_score,
                        "normalized_score": normalized_score,
                        "runtime_sec": runtime,
                        "canonical": canonical,
                        "object": object_data,
                        "error": error,
                    }
                )

        novelty = _novelty_from_scores(evaluations)
        return CandidateFamilyResult(
            program_id=program.program_id,
            domain=program.domain,
            train_scores=split_scores["train"],
            val_scores=split_scores["val"],
            test_scores=split_scores["test"],
            invalid_count=invalid_count,
            mean_runtime_sec=mean(runtimes) if runtimes else 0.0,
            complexity=program.complexity(),
            novelty=novelty,
            evaluations=evaluations,
        )


def _novelty_from_scores(evaluations: list[dict[str, Any]]) -> float:
    values = [round(float(row["normalized_score"]), 4) for row in evaluations]
    return len(set(values)) / max(1, len(values))
