from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


PALETTE = {
    "misr": "#2563eb",
    "unit_square": "#059669",
    "guillotine": "#dc2626",
    "graph_separation": "#7c3aed",
    "epsilon_net": "#d97706",
}


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _xml(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_summary_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bootstrap_ci(values: list[float], *, samples: int = 1000, seed: int = 20260625) -> tuple[float | str, float | str]:
    if not values:
        return "", ""
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(samples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * (samples - 1))]
    hi = means[int(0.975 * (samples - 1))]
    return lo, hi


def build_component_table(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("problem", ""),
            row.get("representation", ""),
            row.get("local_search", ""),
            row.get("surrogate", ""),
            row.get("control_mode", "") or "patternboost",
        )
        groups[key].append(row)
    table = []
    for (problem, representation, local_search, surrogate, control_mode), group in sorted(groups.items()):
        scores = [score for row in group if (score := _float_or_none(row.get("best_exact_score"))) is not None]
        times = [time for row in group if (time := _float_or_none(row.get("time_to_best"))) is not None]
        completed = [
            value
            for row in group
            if (value := _float_or_none(row.get("completed_iterations"))) is not None
        ]
        budget_stopped = sum(1 for row in group if row.get("stop_reason") == "budget_exhausted")
        hashes = [row.get("best_certificate_hash", "") for row in group if row.get("best_certificate_hash")]
        ci_low, ci_high = _bootstrap_ci(scores)
        table.append(
            {
                "problem": problem,
                "representation": representation,
                "local_search": local_search,
                "surrogate": surrogate,
                "control_mode": control_mode,
                "runs_completed": len(group),
                "budget_stopped_runs": budget_stopped,
                "median_completed_iterations": statistics.median(completed) if completed else "",
                "best_verified_score": max(scores) if scores else "",
                "mean_best_verified_score": statistics.fmean(scores) if scores else "",
                "median_best_verified_score": statistics.median(scores) if scores else "",
                "score_stddev": statistics.pstdev(scores) if len(scores) > 1 else 0.0 if scores else "",
                "bootstrap_mean_ci_low": ci_low,
                "bootstrap_mean_ci_high": ci_high,
                "median_time_to_best": statistics.median(times) if times else "",
                "best_certificate_hash": hashes[0] if hashes else "",
            }
        )
    return table


def write_component_csv(table: list[dict[str, Any]], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "problem",
        "representation",
        "local_search",
        "surrogate",
        "control_mode",
        "runs_completed",
        "budget_stopped_runs",
        "median_completed_iterations",
        "best_verified_score",
        "mean_best_verified_score",
        "median_best_verified_score",
        "score_stddev",
        "bootstrap_mean_ci_low",
        "bootstrap_mean_ci_high",
        "median_time_to_best",
        "best_certificate_hash",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in table:
            writer.writerow(row)
    return target


def _fmt(value: Any) -> str:
    number = _float_or_none(value)
    if number is None:
        return "" if value in (None, "") else str(value)
    return f"{number:.6g}"


def write_markdown(table: list[dict[str, Any]], artifacts: dict[str, str], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PatternBoost Multi-Level Run Report",
        "",
        "Generated from structured `run_summary_v1` files.",
        "",
        "## Artifacts",
        "",
    ]
    for label, artifact in artifacts.items():
        lines.append(f"- `{label}`: `{artifact}`")
    lines.extend(
        [
            "",
            "## Component Table",
            "",
            "| Problem | Representation | Local search | Surrogate | Control | Runs | Stops | Iter | Best | Mean | 95% CI | Median | Median time | Hash |",
            "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in table:
        ci = f"[{_fmt(row['bootstrap_mean_ci_low'])}, {_fmt(row['bootstrap_mean_ci_high'])}]"
        lines.append(
            "| {problem} | {representation} | {local_search} | {surrogate} | {control_mode} | {runs_completed} | {stops} | {iters} | {best} | {mean} | {ci} | {median} | {time} | `{hash}` |".format(
                problem=row["problem"],
                representation=row["representation"],
                local_search=row["local_search"],
                surrogate=row["surrogate"],
                control_mode=row["control_mode"],
                runs_completed=row["runs_completed"],
                stops=row["budget_stopped_runs"],
                iters=_fmt(row["median_completed_iterations"]),
                best=_fmt(row["best_verified_score"]),
                mean=_fmt(row["mean_best_verified_score"]),
                ci=ci,
                median=_fmt(row["median_best_verified_score"]),
                time=_fmt(row["median_time_to_best"]),
                hash=row["best_certificate_hash"],
            )
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def write_best_score_svg(table: list[dict[str, Any]], path: str | Path) -> Path:
    best_by_problem: dict[str, float] = {}
    for row in table:
        score = _float_or_none(row.get("best_verified_score"))
        if score is None:
            continue
        problem = str(row.get("problem"))
        best_by_problem[problem] = max(best_by_problem.get(problem, float("-inf")), score)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width = 900
    height = 420
    margin = 70
    labels = sorted(best_by_problem)
    max_score = max(best_by_problem.values(), default=1.0)
    bar_w = (width - 2 * margin) / max(1, len(labels))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Best verified score by problem</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#111827"/>',
    ]
    for idx, label in enumerate(labels):
        score = best_by_problem[label]
        h = (height - 2 * margin) * (score / max_score if max_score > 0 else 0.0)
        x = margin + idx * bar_w + bar_w * 0.18
        y = height - margin - h
        w = bar_w * 0.64
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{PALETTE.get(label, "#2563eb")}" fill-opacity="0.78"/>')
        parts.append(f'<text x="{x + w/2:.2f}" y="{y - 8:.2f}" text-anchor="middle" font-size="13" font-family="monospace">{score:.4g}</text>')
        parts.append(f'<text x="{x + w/2:.2f}" y="{height - margin + 24:.2f}" text-anchor="middle" font-size="12" font-family="monospace">{_xml(label)}</text>')
    parts.append("</svg>\n")
    target.write_text("\n".join(parts), encoding="utf-8")
    return target


def write_ecdf_svg(rows: list[dict[str, str]], path: str | Path) -> Path:
    scores_by_problem: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        score = _float_or_none(row.get("best_exact_score"))
        if score is not None:
            scores_by_problem[row.get("problem", "")].append(score)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height, margin = 920, 460, 70
    all_scores = [score for scores in scores_by_problem.values() for score in scores]
    max_score = max(all_scores, default=1.0)
    min_score = min(all_scores, default=0.0)
    span = max(max_score - min_score, 1e-9)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>ECDF of best verified scores</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<text x="{width/2}" y="34" text-anchor="middle" font-size="18" font-family="monospace">ECDF of best verified scores</text>',
    ]
    for problem, scores in sorted(scores_by_problem.items()):
        if not scores:
            continue
        scores = sorted(scores)
        points = []
        for idx, score in enumerate(scores, start=1):
            x = margin + (score - min_score) / span * (width - 2 * margin)
            y = height - margin - (idx / len(scores)) * (height - 2 * margin)
            points.append(f"{x:.2f},{y:.2f}")
        color = PALETTE.get(problem, "#374151")
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        lx = width - margin - 160
        ly = margin + 22 * len([p for p in sorted(scores_by_problem) if p <= problem])
        parts.append(f'<circle cx="{lx}" cy="{ly}" r="5" fill="{color}"/><text x="{lx+12}" y="{ly+4}" font-size="12" font-family="monospace">{_xml(problem)} n={len(scores)}</text>')
    parts.append("</svg>\n")
    target.write_text("\n".join(parts), encoding="utf-8")
    return target


def write_heatmap_svg(table: list[dict[str, Any]], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows_by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in table:
        if _float_or_none(row.get("best_verified_score")) is not None:
            rows_by_problem[str(row["problem"])].append(row)
    cell_w, cell_h = 96, 28
    label_w, top_h = 250, 62
    panels = []
    y_offset = 0
    for problem, rows in sorted(rows_by_problem.items()):
        y_labels = sorted({f"{row['control_mode']} / {row['representation']} / {row['local_search']}" for row in rows})
        x_labels = sorted({str(row["surrogate"]) for row in rows})
        scores = [_float_or_none(row.get("best_verified_score")) or 0.0 for row in rows]
        max_score = max(scores, default=1.0)
        panel_h = top_h + max(1, len(y_labels)) * cell_h + 24
        panels.append((problem, rows, x_labels, y_labels, max_score, y_offset, panel_h))
        y_offset += panel_h
    width = label_w + max((len(panel[2]) for panel in panels), default=1) * cell_w + 40
    height = max(180, y_offset + 30)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Component heatmap of best verified scores</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for problem, rows, x_labels, y_labels, max_score, y0, _panel_h in panels:
        parts.append(f'<text x="18" y="{y0 + 24}" font-size="17" font-family="monospace" font-weight="700">{_xml(problem)}</text>')
        x_index = {label: idx for idx, label in enumerate(x_labels)}
        y_index = {label: idx for idx, label in enumerate(y_labels)}
        for label, idx in x_index.items():
            x = label_w + idx * cell_w + cell_w / 2
            parts.append(f'<text x="{x:.2f}" y="{y0 + 46}" text-anchor="middle" font-size="10" font-family="monospace">{_xml(label[:18])}</text>')
        for label, idx in y_index.items():
            y = y0 + top_h + idx * cell_h + 18
            parts.append(f'<text x="{label_w - 8}" y="{y:.2f}" text-anchor="end" font-size="10" font-family="monospace">{_xml(label[:34])}</text>')
        for row in rows:
            score = _float_or_none(row.get("best_verified_score")) or 0.0
            y_label = f"{row['control_mode']} / {row['representation']} / {row['local_search']}"
            x = label_w + x_index[str(row["surrogate"])] * cell_w
            y = y0 + top_h + y_index[y_label] * cell_h
            intensity = score / max_score if max_score > 0 else 0.0
            alpha = 0.16 + 0.74 * intensity
            color = PALETTE.get(problem, "#2563eb")
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 3}" height="{cell_h - 3}" fill="{color}" fill-opacity="{alpha:.3f}" stroke="#ffffff"/>')
            parts.append(f'<text x="{x + cell_w/2:.2f}" y="{y + 17:.2f}" text-anchor="middle" font-size="10" font-family="monospace">{score:.3g}</text>')
    parts.append("</svg>\n")
    target.write_text("\n".join(parts), encoding="utf-8")
    return target


def _event_paths(rows: list[dict[str, str]]) -> list[Path]:
    paths: list[Path] = []
    seen = set()
    for row in rows:
        event_stream = row.get("event_stream")
        if not event_stream and row.get("summary_path"):
            try:
                summary = json.loads(Path(row["summary_path"]).read_text(encoding="utf-8"))
                event_stream = summary.get("event_stream")
            except Exception:
                event_stream = None
        if not event_stream:
            continue
        path = Path(event_stream)
        if path.exists() and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def read_event_rows(summary_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    events = []
    for path in _event_paths(summary_rows):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                event["_event_path"] = str(path)
                events.append(event)
    return events


def _stable_id64(value: str) -> int:
    if len(value) >= 16:
        try:
            return int(value[:16], 16)
        except ValueError:
            pass
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def read_event_plot_data(
    summary_rows: list[dict[str, str]],
    *,
    max_scatter_points: int | None = None,
    seed: int = 20260625,
) -> tuple[list[dict[str, Any]], dict[str, list[tuple[int, int]]]]:
    if max_scatter_points is None:
        max_scatter_points = int(os.environ.get("PATTERNBOOST_REPORT_MAX_SCATTER", "50000"))
    rng = random.Random(seed)
    scatter_sample: list[dict[str, Any]] = []
    scatter_seen = 0
    seen_by_problem_gen: dict[tuple[str, int], set[int]] = defaultdict(set)

    for path in _event_paths(summary_rows):
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

                problem = str(event.get("problem", ""))
                candidate_id = event.get("candidate_id")
                if candidate_id:
                    try:
                        generation = int(event.get("generation", 0))
                    except Exception:
                        generation = 0
                    seen_by_problem_gen[(problem, generation)].add(_stable_id64(str(candidate_id)))

                surrogate_score = _float_or_none(event.get("surrogate_score"))
                exact_score = _float_or_none(event.get("exact_score"))
                if surrogate_score is None or exact_score is None:
                    continue
                point = {
                    "schema": "candidate_event_v1",
                    "problem": problem,
                    "surrogate_score": surrogate_score,
                    "exact_score": exact_score,
                }
                scatter_seen += 1
                if max_scatter_points <= 0:
                    continue
                if len(scatter_sample) < max_scatter_points:
                    scatter_sample.append(point)
                else:
                    index = rng.randrange(scatter_seen)
                    if index < max_scatter_points:
                        scatter_sample[index] = point

    series: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (problem, generation), ids in sorted(seen_by_problem_gen.items()):
        series[problem].append((generation, len(ids)))
    return scatter_sample, series


def write_surrogate_scatter_svg(events: list[dict[str, Any]], path: str | Path) -> Path:
    points = [
        event
        for event in events
        if event.get("schema") == "candidate_event_v1"
        and _float_or_none(event.get("surrogate_score")) is not None
        and _float_or_none(event.get("exact_score")) is not None
    ]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height, margin = 900, 520, 74
    x_values = [_float_or_none(event.get("surrogate_score")) or 0.0 for event in points]
    y_values = [_float_or_none(event.get("exact_score")) or 0.0 for event in points]
    x_min, x_max = min(x_values, default=0.0), max(x_values, default=1.0)
    y_min, y_max = min(y_values, default=0.0), max(y_values, default=1.0)
    x_span, y_span = max(x_max - x_min, 1e-9), max(y_max - y_min, 1e-9)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Surrogate score versus exact score</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<text x="{width/2}" y="34" text-anchor="middle" font-size="18" font-family="monospace">Surrogate versus exact audited score</text>',
    ]
    for event in points:
        sx = _float_or_none(event.get("surrogate_score")) or 0.0
        ex = _float_or_none(event.get("exact_score")) or 0.0
        x = margin + (sx - x_min) / x_span * (width - 2 * margin)
        y = height - margin - (ex - y_min) / y_span * (height - 2 * margin)
        problem = str(event.get("problem", ""))
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{PALETTE.get(problem, "#374151")}" fill-opacity="0.58"/>')
    parts.append(f'<text x="{width/2}" y="{height-22}" text-anchor="middle" font-size="12" font-family="monospace">surrogate score</text>')
    parts.append(f'<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle" font-size="12" font-family="monospace">exact score</text>')
    parts.append("</svg>\n")
    target.write_text("\n".join(parts), encoding="utf-8")
    return target


def _diversity_series_from_events(events: list[dict[str, Any]]) -> dict[str, list[tuple[int, int]]]:
    seen_by_problem_gen: dict[tuple[str, int], set[int]] = defaultdict(set)
    for event in events:
        if event.get("schema") != "candidate_event_v1" or not event.get("candidate_id"):
            continue
        try:
            generation = int(event.get("generation", 0))
        except Exception:
            continue
        seen_by_problem_gen[(str(event.get("problem", "")), generation)].add(_stable_id64(str(event["candidate_id"])))
    series: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (problem, generation), ids in sorted(seen_by_problem_gen.items()):
        series[problem].append((generation, len(ids)))
    return series


def write_diversity_series_svg(series: dict[str, list[tuple[int, int]]], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height, margin = 900, 460, 70
    max_gen = max((gen for points in series.values() for gen, _ in points), default=1)
    max_div = max((count for points in series.values() for _, count in points), default=1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Candidate diversity by generation</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#111827"/>',
        f'<text x="{width/2}" y="34" text-anchor="middle" font-size="18" font-family="monospace">Unique audited candidates by generation</text>',
    ]
    for problem, points in sorted(series.items()):
        if not points:
            continue
        color = PALETTE.get(problem, "#374151")
        coords = []
        for gen, count in points:
            x = margin + (gen / max(1, max_gen)) * (width - 2 * margin)
            y = height - margin - (count / max(1, max_div)) * (height - 2 * margin)
            coords.append(f"{x:.2f},{y:.2f}")
        parts.append(f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" stroke-width="2.2"/>')
    parts.append("</svg>\n")
    target.write_text("\n".join(parts), encoding="utf-8")
    return target


def write_diversity_svg(events: list[dict[str, Any]], path: str | Path) -> Path:
    return write_diversity_series_svg(_diversity_series_from_events(events), path)


def generate_report(summary_csv: str | Path, out_dir: str | Path) -> dict[str, str]:
    rows = read_summary_csv(summary_csv)
    table = build_component_table(rows)
    scatter_events, diversity_series = read_event_plot_data(rows)
    out = Path(out_dir)
    component_csv = write_component_csv(table, out / "component_table.csv")
    best_svg = write_best_score_svg(table, out / "best_scores.svg")
    ecdf_svg = write_ecdf_svg(rows, out / "ecdf_scores.svg")
    heatmap_svg = write_heatmap_svg(table, out / "component_heatmap.svg")
    scatter_svg = write_surrogate_scatter_svg(scatter_events, out / "surrogate_exact_scatter.svg")
    diversity_svg = write_diversity_series_svg(diversity_series, out / "candidate_diversity.svg")
    artifacts = {
        "component_table": str(component_csv),
        "best_scores_svg": str(best_svg),
        "ecdf_scores_svg": str(ecdf_svg),
        "component_heatmap_svg": str(heatmap_svg),
        "surrogate_exact_scatter_svg": str(scatter_svg),
        "candidate_diversity_svg": str(diversity_svg),
    }
    markdown = write_markdown(table, artifacts, out / "report.md")
    artifacts["markdown"] = str(markdown)
    return artifacts
