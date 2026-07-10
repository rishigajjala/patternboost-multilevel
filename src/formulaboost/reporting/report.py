from __future__ import annotations

from pathlib import Path
from typing import Any


def write_results_report(
    path: str | Path,
    manifest: dict[str, Any],
    family_rows: list[dict[str, Any]],
    *,
    examples_loaded: int,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    top_rows = sorted(
        family_rows,
        key=lambda row: (
            row["evaluation"]["invalid_rate"],
            -row["evaluation"]["val_mean_score"],
            row["complexity"],
        ),
    )[:20]
    lines = [
        "# FormulaBoost Results",
        "",
        f"- Run ID: `{manifest['run_id']}`",
        f"- Domain: `{manifest['domain']}`",
        f"- Seed: `{manifest['seed']}`",
        f"- Examples loaded: {examples_loaded}",
        f"- Candidate families: {len(family_rows)}",
        "",
        "## Parameter Splits",
        "",
        f"- Train: `{manifest['train_params']}`",
        f"- Validation: `{manifest['val_params']}`",
        f"- Test: `{manifest['test_params']}`",
        "",
        "## Top Families",
        "",
        "| rank | pareto | program | complexity | train | val | test | invalid_rate | runtime |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(top_rows, start=1):
        ev = row["evaluation"]
        lines.append(
            "| {rank} | {pareto} | `{program}` | {complexity} | {train:.3f} | {val:.3f} | "
            "{test:.3f} | {invalid:.3f} | {runtime:.4f}s |".format(
                rank=rank,
                pareto=ev.get("pareto_rank", ""),
                program=row["pretty"].replace("|", "\\|"),
                complexity=row["complexity"],
                train=ev["train_mean_score"],
                val=ev["val_mean_score"],
                test=ev["test_mean_score"],
                invalid=ev["invalid_rate"],
                runtime=ev["mean_runtime_sec"],
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Scores are normalized by `raw_score / sqrt(n)` for valid domain objects. Invalid outputs receive a fixed penalty.",
        ]
    )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
