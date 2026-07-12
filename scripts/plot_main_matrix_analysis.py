#!/usr/bin/env python3
"""Create publication figures and descriptive tables for the 81-row matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from matplotlib.colors import Normalize
    from scipy.stats import spearmanr
except ImportError as exc:  # pragma: no cover - dependency guidance for users
    raise SystemExit(
        "analysis dependencies are missing; install matplotlib, numpy, pandas, and scipy"
    ) from exc


PROBLEM_ORDER = ["misr", "unit_square", "guillotine"]
COMPONENTS = {
    "misr": {
        "representation": [
            "fixed_symmetry_rectangles",
            "triangle_free_rect",
            "quadratic_program_rectangles",
        ],
        "local_search": [
            "sequence_pair_pivot",
            "symmetry_crossover_hillclimb",
            "program_coeff_pivot",
        ],
        "surrogate": [
            "exact_lp_gap_pressure",
            "triangle_free_exact_gap_pressure",
            "graph_conflict_proxy",
        ],
    },
    "unit_square": {
        "representation": ["fixed_symmetry_grid", "line_square_incidence", "sqstab_exact_grid"],
        "local_search": [
            "coord_mutation",
            "symmetry_crossover_hillclimb",
            "sqstab_local_hillclimb",
        ],
        "surrogate": [
            "greedy_partial_lp_bitset",
            "exact_stab_gap_pressure",
            "incidence_statistics",
        ],
    },
    "guillotine": {
        "representation": [
            "rect_direct_disjoint",
            "fixed_symmetry_packing",
            "recursive_obstruction_grammar",
        ],
        "local_search": [
            "packing_resize",
            "symmetry_crossover_hillclimb",
            "witness_breaking",
        ],
        "surrogate": [
            "first_cut_obstruction",
            "depth_limited_dp",
            "k_subset_nonseparability",
        ],
    },
}

PROBLEM_LABELS = {
    "misr": "MISR LP gap",
    "unit_square": "Unit-square stabbing",
    "guillotine": "Guillotine hardness",
}

COLORS = ["#2563eb", "#dc2626", "#059669"]


def _label(value: str, width: int = 20) -> str:
    words = value.replace("_", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if current and len(trial) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return "\n".join(lines)


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#4b5563",
            "axes.labelcolor": "#111827",
            "axes.titlecolor": "#111827",
            "axes.grid": True,
            "grid.color": "#d1d5db",
            "grid.linewidth": 0.55,
            "grid.alpha": 0.65,
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "legend.frameon": False,
            "savefig.bbox": "tight",
        }
    )


def _save(fig, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", dpi=220, facecolor="white")
    fig.savefig(out_dir / f"{stem}.pdf", facecolor="white")
    plt.close(fig)


def _safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _curve_points(
    improvements: pd.DataFrame,
    metric: pd.Series,
    *,
    axis: str,
) -> tuple[np.ndarray, np.ndarray]:
    axis_column = {
        "generation": "generation",
        "model_epoch": "cumulative_model_epochs",
        "elapsed_seconds": "elapsed_seconds",
    }[axis]
    total_column = {
        "generation": "completed_iterations",
        "model_epoch": "total_model_epochs",
        "elapsed_seconds": "elapsed_seconds",
    }[axis]
    subset = improvements.sort_values(axis_column)
    xs = _safe_float(subset[axis_column]).to_numpy(dtype=float)
    ys = _safe_float(subset["best_score"]).to_numpy(dtype=float)
    valid = np.isfinite(xs) & np.isfinite(ys)
    xs, ys = xs[valid], ys[valid]
    total = float(metric.get(total_column) or 0.0)
    final_score = float(metric.get("best_score"))
    if xs.size == 0:
        return np.array([0.0, total]), np.array([final_score, final_score])
    if xs[0] > 0:
        xs = np.insert(xs, 0, 0.0)
        ys = np.insert(ys, 0, ys[0])
    endpoint = max(total, float(xs[-1]))
    if endpoint > xs[-1]:
        xs = np.append(xs, endpoint)
        ys = np.append(ys, final_score)
    return xs, ys


def plot_configuration_trajectories(
    metrics: pd.DataFrame,
    improvements: pd.DataFrame,
    out_dir: Path,
    *,
    axis: str,
) -> None:
    axis_label = {
        "generation": "Search generation",
        "model_epoch": "Cumulative transformer training epoch",
        "elapsed_seconds": "Elapsed time (hours)",
    }[axis]
    for problem in PROBLEM_ORDER:
        levels = COMPONENTS[problem]
        fig, axes = plt.subplots(3, 3, figsize=(13.2, 10.4), sharey=True)
        problem_metrics = metrics[metrics["problem"] == problem].set_index("config_id")
        problem_improvements = improvements[improvements["problem"] == problem]
        for row_idx, representation in enumerate(levels["representation"]):
            for col_idx, local_search in enumerate(levels["local_search"]):
                ax = axes[row_idx, col_idx]
                for surrogate_idx, surrogate in enumerate(levels["surrogate"]):
                    config_id = "/".join((problem, representation, local_search, surrogate))
                    if config_id not in problem_metrics.index:
                        continue
                    metric = problem_metrics.loc[config_id]
                    subset = problem_improvements[problem_improvements["config_id"] == config_id]
                    xs, ys = _curve_points(subset, metric, axis=axis)
                    if axis == "elapsed_seconds":
                        xs = xs / 3600.0
                    ax.step(
                        xs,
                        ys,
                        where="post",
                        color=COLORS[surrogate_idx],
                        linewidth=1.55,
                        label=_label(surrogate, 18),
                    )
                    ax.scatter(xs[:-1], ys[:-1], s=9, color=COLORS[surrogate_idx], zorder=3)
                if row_idx == 0:
                    ax.set_title(_label(local_search, 22), fontsize=10, fontweight="bold")
                if col_idx == 0:
                    ax.set_ylabel(f"{_label(representation, 18)}\nBest exact score", fontsize=8.5)
                if row_idx == 2:
                    ax.set_xlabel(axis_label, fontsize=8.5)
                ax.tick_params(labelsize=7.5)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.985), fontsize=8.5)
        fig.suptitle(
            f"{PROBLEM_LABELS[problem]}: all 27 configurations",
            fontsize=15,
            fontweight="bold",
            y=1.025,
        )
        fig.text(
            0.5,
            0.002,
            "Rows are representations, columns are local-search operators, and colors are surrogates.",
            ha="center",
            fontsize=8.5,
            color="#374151",
        )
        fig.tight_layout(rect=(0, 0.025, 1, 0.95))
        _save(fig, out_dir, f"fig_{problem}_27_trajectories_{axis}")


def plot_normalized_overview(
    curves: pd.DataFrame, metrics: pd.DataFrame, out_dir: Path
) -> None:
    subset = curves[curves["axis"] == "model_epoch"].copy()
    trained_ids = set(
        metrics.loc[_safe_float(metrics["total_model_epochs"]) > 0, "config_id"]
    )
    subset = subset[subset["config_id"].isin(trained_ids)]
    subset["best_score"] = _safe_float(subset["best_score"])
    subset = subset.sort_values(["config_id", "progress_percent"])
    subset["best_score"] = subset.groupby("config_id")["best_score"].transform(
        lambda values: values.ffill().bfill()
    )
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.4))
    for ax, problem in zip(axes, PROBLEM_ORDER):
        data = subset[subset["problem"] == problem]
        for _, config in data.groupby("config_id"):
            ax.step(
                config["progress_percent"],
                config["best_score"],
                where="post",
                color="#9ca3af",
                alpha=0.42,
                linewidth=0.7,
            )
        aggregate = data.groupby("progress_percent")["best_score"]
        x = np.array(sorted(data["progress_percent"].unique()), dtype=float)
        median = aggregate.median().reindex(x).to_numpy(dtype=float)
        q1 = aggregate.quantile(0.25).reindex(x).to_numpy(dtype=float)
        q3 = aggregate.quantile(0.75).reindex(x).to_numpy(dtype=float)
        ax.fill_between(x, q1, q3, color="#93c5fd", alpha=0.45, label="middle 50%")
        ax.step(x, median, where="post", color="#1d4ed8", linewidth=2.2, label="median")
        ax.set_title(PROBLEM_LABELS[problem], fontweight="bold")
        ax.set_xlabel("Fraction of available model-training epochs (%)")
        ax.set_ylabel("Best exact score")
        ax.set_xlim(0, 100)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.04))
    fig.suptitle(
        "Learning behavior across configurations with model training",
        fontsize=14,
        fontweight="bold",
        y=1.11,
    )
    fig.tight_layout()
    _save(fig, out_dir, "fig_all_81_normalized_epoch_curves")


def plot_heatmaps(metrics: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(13.5, 12.6))
    for problem_idx, problem in enumerate(PROBLEM_ORDER):
        levels = COMPONENTS[problem]
        problem_data = metrics[metrics["problem"] == problem]
        low = float(problem_data["best_score"].min())
        high = float(problem_data["best_score"].max())
        norm = Normalize(vmin=low, vmax=high if high > low else low + 1e-9)
        for rep_idx, representation in enumerate(levels["representation"]):
            ax = axes[problem_idx, rep_idx]
            matrix = np.full((3, 3), np.nan)
            for local_idx, local_search in enumerate(levels["local_search"]):
                for surrogate_idx, surrogate in enumerate(levels["surrogate"]):
                    match = problem_data[
                        (problem_data["representation"] == representation)
                        & (problem_data["local_search"] == local_search)
                        & (problem_data["surrogate"] == surrogate)
                    ]
                    if not match.empty:
                        matrix[local_idx, surrogate_idx] = float(match.iloc[0]["best_score"])
            image = ax.imshow(matrix, cmap="viridis", norm=norm, aspect="auto")
            for i in range(3):
                for j in range(3):
                    if not np.isfinite(matrix[i, j]):
                        continue
                    rgba = image.cmap(norm(matrix[i, j]))
                    luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                    ax.text(
                        j,
                        i,
                        f"{matrix[i, j]:.3f}",
                        ha="center",
                        va="center",
                        color="black" if luminance > 0.58 else "white",
                        fontsize=8.5,
                        fontweight="bold",
                    )
            ax.set_xticks(range(3), [_label(value, 14) for value in levels["surrogate"]], fontsize=7.2)
            ax.set_yticks(range(3), [_label(value, 16) for value in levels["local_search"]], fontsize=7.2)
            ax.set_title(_label(representation, 22), fontsize=10, fontweight="bold")
            if rep_idx == 0:
                ax.set_ylabel(f"{PROBLEM_LABELS[problem]}\nLocal search", fontsize=9.5)
            if problem_idx == 2:
                ax.set_xlabel("Surrogate", fontsize=9)
    fig.suptitle("Final exact score for every matrix cell", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()
    _save(fig, out_dir, "fig_final_score_heatmaps_81")


def factor_marginals(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for problem in PROBLEM_ORDER:
        data = metrics[metrics["problem"] == problem]
        for factor in ("representation", "local_search", "surrogate"):
            for level, values in data.groupby(factor)["best_score"]:
                numeric = _safe_float(values).dropna().to_numpy(dtype=float)
                rows.append(
                    {
                        "problem": problem,
                        "factor": factor,
                        "level": level,
                        "count": len(numeric),
                        "mean": float(np.mean(numeric)),
                        "median": float(np.median(numeric)),
                        "minimum": float(np.min(numeric)),
                        "maximum": float(np.max(numeric)),
                        "q1": float(np.quantile(numeric, 0.25)),
                        "q3": float(np.quantile(numeric, 0.75)),
                    }
                )
    return pd.DataFrame(rows)


def plot_factor_marginals(metrics: pd.DataFrame, marginals: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(14.5, 11.7))
    factors = ["representation", "local_search", "surrogate"]
    rng = np.random.default_rng(20260710)
    for problem_idx, problem in enumerate(PROBLEM_ORDER):
        for factor_idx, factor in enumerate(factors):
            ax = axes[problem_idx, factor_idx]
            levels = COMPONENTS[problem][factor]
            data = metrics[metrics["problem"] == problem]
            stats = marginals[(marginals["problem"] == problem) & (marginals["factor"] == factor)].set_index("level")
            for idx, level in enumerate(levels):
                values = _safe_float(data[data[factor] == level]["best_score"]).dropna().to_numpy(dtype=float)
                jitter = rng.normal(0.0, 0.045, len(values))
                ax.scatter(
                    np.full(len(values), idx) + jitter,
                    values,
                    s=20,
                    color="#9ca3af",
                    alpha=0.7,
                    zorder=2,
                )
                if level in stats.index:
                    ax.scatter(idx, stats.loc[level, "mean"], marker="D", s=48, color="#dc2626", label="mean" if idx == 0 else None, zorder=4)
                    ax.scatter(idx, stats.loc[level, "median"], marker="_", s=180, linewidth=2.2, color="#1d4ed8", label="median" if idx == 0 else None, zorder=4)
            ax.set_xticks(range(len(levels)), [_label(value, 15) for value in levels], fontsize=7.5)
            ax.set_ylabel("Final exact score")
            if problem_idx == 0:
                ax.set_title(_label(factor, 18).title(), fontweight="bold")
            if factor_idx == 0:
                ax.text(
                    -0.29,
                    0.5,
                    PROBLEM_LABELS[problem],
                    transform=ax.transAxes,
                    rotation=90,
                    va="center",
                    ha="center",
                    fontweight="bold",
                    fontsize=10,
                )
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.015))
    fig.suptitle("Descriptive marginal contrasts for each component", fontsize=15, fontweight="bold", y=1.055)
    fig.tight_layout()
    _save(fig, out_dir, "fig_component_marginal_effects")


def early_final_rank_table(curves: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    subset = curves[curves["axis"] == "model_epoch"].copy()
    subset["best_score"] = _safe_float(subset["best_score"])
    rows: list[dict[str, object]] = []
    trained = metrics[_safe_float(metrics["total_model_epochs"]) > 0]
    final_scores = trained.set_index("config_id")["best_score"]
    for problem in PROBLEM_ORDER:
        for percent in (1, 5, 10, 25, 50, 75):
            early = subset[(subset["problem"] == problem) & (subset["progress_percent"] == percent)].set_index("config_id")["best_score"]
            joined = pd.concat([early.rename("early"), final_scores.rename("final")], axis=1).dropna()
            joined = joined.loc[[idx for idx in joined.index if idx.startswith(problem + "/")]]
            if len(joined) >= 3 and joined["early"].nunique() > 1 and joined["final"].nunique() > 1:
                correlation, p_value = spearmanr(joined["early"], joined["final"])
            else:
                correlation, p_value = float("nan"), float("nan")
            rows.append(
                {
                    "problem": problem,
                    "epoch_progress_percent": percent,
                    "rows": len(joined),
                    "spearman_rho": correlation,
                    "descriptive_p_value": p_value,
                }
            )
    return pd.DataFrame(rows)


def plot_early_rank(rank_table: pd.DataFrame, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.7))
    for idx, problem in enumerate(PROBLEM_ORDER):
        data = rank_table[rank_table["problem"] == problem]
        ax.plot(
            data["epoch_progress_percent"],
            data["spearman_rho"],
            marker="o",
            linewidth=2.0,
            color=COLORS[idx],
            label=PROBLEM_LABELS[problem],
        )
    ax.axhline(0, color="#6b7280", linewidth=0.8)
    ax.set_ylim(-1.02, 1.02)
    ax.set_xlabel("Fraction of available model-training epochs (%)")
    ax.set_ylabel("Spearman rank correlation with final score")
    ax.set_title("How early does the final configuration ranking become predictable?", fontweight="bold")
    ax.legend(loc="lower right")
    _save(fig, out_dir, "fig_early_to_final_rank_stability")


def plot_plateaus(metrics: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12.8, 11.0))
    for row_idx, problem in enumerate(PROBLEM_ORDER):
        data = metrics[metrics["problem"] == problem].copy()
        data["best_epoch_fraction"] = np.where(
            _safe_float(data["total_model_epochs"]) > 0,
            _safe_float(data["best_model_epoch"]) / _safe_float(data["total_model_epochs"]),
            np.nan,
        )
        ax = axes[row_idx, 0]
        scatter = ax.scatter(
            100 * data["best_epoch_fraction"],
            data["best_score"],
            c=np.log10(np.maximum(_safe_float(data["generation_rate_per_hour"]), 1.0)),
            cmap="plasma",
            s=55,
            edgecolor="white",
            linewidth=0.5,
        )
        ax.set_xlabel("Epoch budget consumed when final best first appeared (%)")
        ax.set_ylabel("Final exact score")
        ax.set_title(f"{PROBLEM_LABELS[problem]}: time of last improvement", fontweight="bold")
        colorbar = fig.colorbar(scatter, ax=ax, pad=0.015)
        colorbar.set_label("log10 generations/hour", fontsize=8)

        ax = axes[row_idx, 1]
        plateau = 100 * _safe_float(data["plateau_fraction"]).dropna().to_numpy(dtype=float)
        ax.hist(plateau, bins=np.linspace(0, 100, 11), color=COLORS[row_idx], alpha=0.78, edgecolor="white")
        if plateau.size:
            ax.axvline(np.median(plateau), color="#111827", linestyle="--", linewidth=1.5, label=f"median {np.median(plateau):.0f}%")
        ax.set_xlabel("Fraction of generations after the last improvement (%)")
        ax.set_ylabel("Configurations")
        ax.set_title(f"{PROBLEM_LABELS[problem]}: plateau length", fontweight="bold")
        ax.legend()
    fig.suptitle("Plateau diagnostics", fontsize=15, fontweight="bold", y=1.015)
    fig.tight_layout()
    _save(fig, out_dir, "fig_plateau_diagnostics")


def _source_family(source: str) -> str:
    source = str(source or "unknown")
    if source == "model_sample":
        return "model sample"
    if source in {"local_mutation", "initial_or_local"}:
        return "initial/local path"
    if source in {"initial", "random_reseed"}:
        return "initial/reseed"
    if source.startswith("fallback_floor"):
        return "fallback"
    if source == "summary_or_checkpoint":
        return "recovered endpoint"
    return "other"


def plot_improvement_sources(improvements: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    data = improvements.copy()
    data["source_family"] = data["source_type"].map(_source_family)
    counts = data.groupby(["problem", "source_family"]).size().rename("improvements").reset_index()
    categories = [
        "initial/reseed",
        "initial/local path",
        "model sample",
        "fallback",
        "recovered endpoint",
        "other",
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    bottom = np.zeros(len(PROBLEM_ORDER), dtype=float)
    palette = ["#6b7280", "#2563eb", "#059669", "#dc2626", "#a855f7", "#d97706"]
    for category, color in zip(categories, palette):
        values = np.array(
            [
                counts.loc[
                    (counts["problem"] == problem) & (counts["source_family"] == category),
                    "improvements",
                ].sum()
                for problem in PROBLEM_ORDER
            ],
            dtype=float,
        )
        if not values.any():
            continue
        ax.bar(PROBLEM_ORDER, values, bottom=bottom, label=category, color=color)
        bottom += values
    ax.set_xticks(range(3), [PROBLEM_LABELS[problem] for problem in PROBLEM_ORDER])
    ax.set_ylabel("Number of strict best-score improvements")
    ax.set_title("Where did improvements come from?", fontweight="bold")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    _save(fig, out_dir, "fig_improvement_sources")
    return counts


def plot_throughput(metrics: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.5))
    for ax, problem in zip(axes, PROBLEM_ORDER):
        data = metrics[metrics["problem"] == problem]
        levels = COMPONENTS[problem]["surrogate"]
        for idx, surrogate in enumerate(levels):
            subset = data[data["surrogate"] == surrogate]
            ax.scatter(
                subset["generation_rate_per_hour"],
                subset["best_score"],
                s=48,
                alpha=0.82,
                color=COLORS[idx],
                label=_label(surrogate, 18),
            )
        positive = _safe_float(data["generation_rate_per_hour"]).dropna()
        if (positive > 0).all() and positive.max() / max(positive.min(), 1e-9) > 20:
            ax.set_xscale("log")
        ax.set_xlabel("Search generations per hour")
        ax.set_ylabel("Final exact score")
        ax.set_title(PROBLEM_LABELS[problem], fontweight="bold")
        ax.legend(fontsize=7.2)
    fig.suptitle("Search throughput versus solution quality", fontsize=14, fontweight="bold", y=1.03)
    fig.tight_layout()
    _save(fig, out_dir, "fig_throughput_vs_quality")


def plot_search_efficiency(metrics: pd.DataFrame, out_dir: Path) -> None:
    diagnostics = [
        ("duplicates_per_generation", "Duplicate candidates per generation"),
        ("model_samples_valid_fraction", "Valid learned-model samples"),
        ("repairs_per_generation", "Representation repairs per generation"),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(14.2, 11.0))
    for problem_idx, problem in enumerate(PROBLEM_ORDER):
        data = metrics[metrics["problem"] == problem]
        representations = COMPONENTS[problem]["representation"]
        for diagnostic_idx, (column, label) in enumerate(diagnostics):
            ax = axes[problem_idx, diagnostic_idx]
            for rep_idx, representation in enumerate(representations):
                subset = data[data["representation"] == representation]
                x = _safe_float(subset[column])
                if column == "model_samples_valid_fraction":
                    x = 100.0 * x
                ax.scatter(
                    x,
                    subset["best_score"],
                    s=46,
                    alpha=0.8,
                    color=COLORS[rep_idx],
                    label=_label(representation, 18),
                )
            if diagnostic_idx == 0:
                ax.set_ylabel(f"{PROBLEM_LABELS[problem]}\nFinal exact score", fontsize=9)
            else:
                ax.set_ylabel("Final exact score", fontsize=8)
            if problem_idx == 0:
                ax.set_title(label, fontweight="bold", fontsize=10)
            if problem_idx == 2:
                suffix = " (%)" if column == "model_samples_valid_fraction" else ""
                ax.set_xlabel(label + suffix, fontsize=8.5)
            if diagnostic_idx == 2:
                ax.legend(fontsize=7, loc="best")
    fig.suptitle(
        "Search-efficiency diagnostics: duplication, model yield, and repair pressure",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    _save(fig, out_dir, "fig_search_efficiency_diagnostics")


def problem_summary(metrics: pd.DataFrame, improvements: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for problem in PROBLEM_ORDER:
        data = metrics[metrics["problem"] == problem].copy()
        scores = _safe_float(data["best_score"]).dropna().to_numpy(dtype=float)
        plateau = _safe_float(data["plateau_fraction"]).dropna().to_numpy(dtype=float)
        gains = _safe_float(data["score_gain"]).dropna().to_numpy(dtype=float)
        duplicates = _safe_float(data["duplicates_per_generation"]).dropna().to_numpy(dtype=float)
        duplicate_slots = _safe_float(data["duplicate_slot_fraction"]).dropna().to_numpy(dtype=float)
        repairs = _safe_float(data["repairs_per_generation"]).dropna().to_numpy(dtype=float)
        model_valid = _safe_float(data["model_samples_valid_fraction"]).dropna().to_numpy(dtype=float)
        model_calls = _safe_float(data["model_train_calls"]).dropna().to_numpy(dtype=float)
        sources = improvements[improvements["problem"] == problem]["source_type"].map(_source_family)
        source_counts = sources.value_counts()
        top = data.sort_values(
            ["best_score", "time_to_best_seconds"], ascending=[False, True]
        ).iloc[0]
        rows.append(
            {
                "problem": problem,
                "rows": len(data),
                "minimum_score": float(np.min(scores)),
                "q1_score": float(np.quantile(scores, 0.25)),
                "median_score": float(np.median(scores)),
                "q3_score": float(np.quantile(scores, 0.75)),
                "maximum_score": float(np.max(scores)),
                "rows_at_maximum": int(np.sum(np.isclose(scores, np.max(scores), atol=1e-12))),
                "mean_score_gain": float(np.mean(gains)) if gains.size else float("nan"),
                "median_plateau_fraction": float(np.median(plateau)) if plateau.size else float("nan"),
                "model_improvement_fraction": (
                    float(source_counts.get("model sample", 0) / source_counts.sum())
                    if source_counts.sum()
                    else float("nan")
                ),
                "median_duplicates_per_generation": float(np.median(duplicates)) if duplicates.size else float("nan"),
                "median_duplicate_slot_fraction": (
                    float(np.median(duplicate_slots)) if duplicate_slots.size else float("nan")
                ),
                "median_repairs_per_generation": float(np.median(repairs)) if repairs.size else float("nan"),
                "median_model_valid_fraction": float(np.median(model_valid)) if model_valid.size else float("nan"),
                "median_model_train_calls": float(np.median(model_calls)) if model_calls.size else float("nan"),
                "top_config_id": top["config_id"],
                "top_best_generation": top["best_generation"],
                "top_best_model_epoch": top["best_model_epoch"],
                "top_time_to_best_seconds": top["time_to_best_seconds"],
                "top_n_items": top["n_items"],
            }
        )
    return pd.DataFrame(rows)


def write_findings(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    marginals: pd.DataFrame,
    rank_table: pd.DataFrame,
    out_dir: Path,
) -> None:
    findings: dict[str, object] = {
        "schema": "patternboost_descriptive_findings_v1",
        "caution": (
            "The matrix has one fresh random run per configuration and no repeated-seed axis. "
            "Component levels are partially confounded with runtime regime; all effects are "
            "descriptive, not sampling-based confidence statements."
        ),
        "problems": {},
    }
    for problem in PROBLEM_ORDER:
        row = summary[summary["problem"] == problem].iloc[0]
        problem_marginals = marginals[marginals["problem"] == problem]
        best_levels = {}
        for factor in ("representation", "local_search", "surrogate"):
            factor_rows = problem_marginals[problem_marginals["factor"] == factor]
            best = factor_rows.sort_values(["mean", "maximum"], ascending=False).iloc[0]
            best_levels[factor] = {
                "level": best["level"],
                "mean": float(best["mean"]),
                "median": float(best["median"]),
                "maximum": float(best["maximum"]),
            }
        rank25 = rank_table[
            (rank_table["problem"] == problem) & (rank_table["epoch_progress_percent"] == 25)
        ].iloc[0]
        findings["problems"][problem] = {
            key: (value.item() if hasattr(value, "item") else value)
            for key, value in row.to_dict().items()
        }
        findings["problems"][problem]["best_descriptive_component_levels"] = best_levels
        findings["problems"][problem]["rank_correlation_at_25_percent_epochs"] = (
            None if pd.isna(rank25["spearman_rho"]) else float(rank25["spearman_rho"])
        )
    (out_dir / "analysis_findings.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot compact PatternBoost 81-row analysis data.")
    parser.add_argument("analysis_dir", type=Path, help="directory created by compact_main_matrix_events.py")
    parser.add_argument("--out-dir", type=Path, required=True, help="figure and table output directory")
    args = parser.parse_args()

    metrics = pd.read_csv(args.analysis_dir / "row_metrics.csv")
    improvements = pd.read_csv(args.analysis_dir / "score_improvements.csv")
    curves = pd.read_csv(args.analysis_dir / "normalized_learning_curves.csv")
    for column in (
        "best_score",
        "initial_best_score",
        "score_gain",
        "completed_iterations",
        "elapsed_seconds",
        "generation_rate_per_hour",
        "total_model_epochs",
        "best_model_epoch",
        "time_to_best_seconds",
        "plateau_fraction",
        "n_items",
        "duplicates_per_generation",
        "model_samples_valid_fraction",
        "repairs_per_generation",
    ):
        if column in metrics:
            metrics[column] = _safe_float(metrics[column])

    _style()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for axis in ("model_epoch", "generation", "elapsed_seconds"):
        plot_configuration_trajectories(metrics, improvements, args.out_dir, axis=axis)
    plot_normalized_overview(curves, metrics, args.out_dir)
    plot_heatmaps(metrics, args.out_dir)
    marginals = factor_marginals(metrics)
    plot_factor_marginals(metrics, marginals, args.out_dir)
    rank_table = early_final_rank_table(curves, metrics)
    plot_early_rank(rank_table, args.out_dir)
    plot_plateaus(metrics, args.out_dir)
    source_counts = plot_improvement_sources(improvements, args.out_dir)
    plot_throughput(metrics, args.out_dir)
    plot_search_efficiency(metrics, args.out_dir)
    summary = problem_summary(metrics, improvements)

    metrics.sort_values(["problem", "best_score"], ascending=[True, False]).to_csv(
        args.out_dir / "configuration_ranking.csv", index=False
    )
    marginals.to_csv(args.out_dir / "factor_marginals.csv", index=False)
    rank_table.to_csv(args.out_dir / "early_final_rank.csv", index=False)
    source_counts.to_csv(args.out_dir / "improvement_sources.csv", index=False)
    summary.to_csv(args.out_dir / "problem_summary.csv", index=False)
    write_findings(metrics, summary, marginals, rank_table, args.out_dir)
    print(f"wrote analysis figures and tables to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
