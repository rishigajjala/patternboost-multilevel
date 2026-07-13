#!/usr/bin/env python3
"""Plot final-matrix convergence slices as dependency-free SVG files."""

from __future__ import annotations

import argparse
import csv
import html
from collections import defaultdict
from pathlib import Path
from typing import Any


DIMENSIONS = ("representation", "local_search", "surrogate")
COLORS = ("#176B87", "#C44900", "#6A4C93")


def _label(value: str) -> str:
    return value.replace("_", " ")


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _winner(rows: list[dict[str, str]], problem: str) -> dict[str, str]:
    candidates = [row for row in rows if row["problem"] == problem]
    if not candidates:
        raise ValueError(f"no final rows for problem {problem!r}")
    return min(
        candidates,
        key=lambda row: (
            -_float(row.get("best_score")),
            _float(row.get("time_to_best_seconds"), float("inf")),
            row["config_id"],
        ),
    )


def _slice_configs(
    rows: list[dict[str, str]], winner: dict[str, str], varied: str
) -> list[dict[str, str]]:
    selected = []
    for row in rows:
        if row["problem"] != winner["problem"]:
            continue
        if any(row[dimension] != winner[dimension] for dimension in DIMENSIONS if dimension != varied):
            continue
        selected.append(row)
    return sorted(selected, key=lambda row: row[varied])


def _history_by_config(rows: list[dict[str, str]]) -> dict[str, list[tuple[float, float, int]]]:
    grouped: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
    for row in rows:
        grouped[row["config_id"]].append(
            (
                _float(row.get("cumulative_model_epochs")),
                _float(row.get("best_score")),
                int(_float(row.get("sequence"))),
            )
        )
    for trace in grouped.values():
        trace.sort(key=lambda point: (point[0], point[2]))
    return grouped


def _step_path(
    trace: list[tuple[float, float, int]],
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> str:
    def x_coord(value: float) -> float:
        return x0 + width * value / max(1.0, x_max)

    def y_coord(value: float) -> float:
        return y0 + height * (y_max - value) / max(1e-12, y_max - y_min)

    if not trace:
        return ""
    first_x, first_y, _ = trace[0]
    commands = [f"M{x_coord(first_x):.2f},{y_coord(first_y):.2f}"]
    for epoch, score, _ in trace[1:]:
        commands.append(f"H{x_coord(epoch):.2f}")
        commands.append(f"V{y_coord(score):.2f}")
    return " ".join(commands)


def plot_problem(
    rows: list[dict[str, str]],
    histories: dict[str, list[tuple[float, float, int]]],
    *,
    problem: str,
    out_dir: Path,
) -> None:
    winner = _winner(rows, problem)
    width, height = 1530, 510
    panel_width = 480
    panel_lefts = (55, 550, 1045)
    plot_top, plot_height, plot_width = 115, 275, 415
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#20252b}'
        '.title{font-size:20px;font-weight:700}.subtitle{font-size:12px}'
        '.axis{font-size:11px}.legend{font-size:11px}</style>',
        f'<text class="title" x="{width / 2}" y="29" text-anchor="middle">'
        f'{html.escape(_label(problem).title())}: component-slice convergence around the best final cell</text>',
    ]
    for panel_index, (left, varied) in enumerate(zip(panel_lefts, DIMENSIONS)):
        selected = _slice_configs(rows, winner, varied)
        traces = [histories.get(row["config_id"], []) for row in selected]
        all_points = [point for trace in traces for point in trace]
        x_max = max((point[0] for point in all_points), default=1.0)
        scores = [point[1] for point in all_points]
        y_min = min(scores, default=0.0)
        y_max = max(scores, default=1.0)
        padding = max(0.02, (y_max - y_min) * 0.12)
        y_min -= padding
        y_max += padding
        held = [
            f"{_label(dimension)}={_label(winner[dimension])}"
            for dimension in DIMENSIONS
            if dimension != varied
        ]
        center = left + panel_width / 2
        parts.extend(
            [
                f'<text class="subtitle" x="{center}" y="56" text-anchor="middle" font-weight="700">'
                f'Vary {html.escape(_label(varied))}</text>',
                f'<text class="subtitle" x="{center}" y="74" text-anchor="middle">'
                f'{html.escape(held[0])}</text>',
                f'<text class="subtitle" x="{center}" y="91" text-anchor="middle">'
                f'{html.escape(held[1])}</text>',
                f'<line x1="{left}" y1="{plot_top + plot_height}" x2="{left + plot_width}" '
                f'y2="{plot_top + plot_height}" stroke="#525b66"/>',
                f'<line x1="{left}" y1="{plot_top}" x2="{left}" y2="{plot_top + plot_height}" '
                f'stroke="#525b66"/>',
            ]
        )
        for tick in range(5):
            x = left + plot_width * tick / 4
            epoch = x_max * tick / 4
            y = plot_top + plot_height * tick / 4
            score = y_max - (y_max - y_min) * tick / 4
            parts.extend(
                [
                    f'<line x1="{x:.2f}" y1="{plot_top}" x2="{x:.2f}" y2="{plot_top + plot_height}" '
                    f'stroke="#d8dde3" stroke-width="0.7"/>',
                    f'<text class="axis" x="{x:.2f}" y="{plot_top + plot_height + 18}" '
                    f'text-anchor="middle">{epoch:.0f}</text>',
                    f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" '
                    f'stroke="#d8dde3" stroke-width="0.7"/>',
                    f'<text class="axis" x="{left - 7}" y="{y + 4:.2f}" text-anchor="end">{score:.3f}</text>',
                ]
            )
        for color, row, trace in zip(COLORS, selected, traces):
            path = _step_path(
                trace,
                x0=left,
                y0=plot_top,
                width=plot_width,
                height=plot_height,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
            )
            parts.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" '
                f'stroke-linejoin="round"/>'
            )
        legend_y = 432
        for index, (color, row) in enumerate(zip(COLORS, selected)):
            y = legend_y + index * 19
            parts.extend(
                [
                    f'<line x1="{left}" y1="{y}" x2="{left + 24}" y2="{y}" '
                    f'stroke="{color}" stroke-width="3"/>',
                    f'<text class="legend" x="{left + 31}" y="{y + 4}">'
                    f'{html.escape(_label(row[varied]))}</text>',
                ]
            )
        parts.append(
            f'<text class="axis" x="{center}" y="{plot_top + plot_height + 40}" '
            f'text-anchor="middle">Cumulative transformer-training epochs</text>'
        )
        if panel_index == 0:
            parts.append(
                f'<text class="axis" transform="translate(14 {plot_top + plot_height / 2}) rotate(-90)" '
                f'text-anchor="middle">Best exact score so far</text>'
            )
    parts.append("</svg>")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"fig_{problem}_component_slices_model_epoch.svg"
    target.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = _read_csv(args.runs)
    histories = _history_by_config(_read_csv(args.history))
    for problem in ("misr", "unit_square", "guillotine"):
        plot_problem(rows, histories, problem=problem, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
