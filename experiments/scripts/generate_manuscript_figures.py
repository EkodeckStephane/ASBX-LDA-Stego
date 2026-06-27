from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT.parent / "paper"
FIGURES = PAPER / "figures"
RESULTS = ROOT / "results" / "confirmation_domains.csv"

BLUE = "#2457A6"
TEAL = "#2A9D8F"
ORANGE = "#E68A2E"
RED = "#C84B31"
GRAY = "#667085"
LIGHT = "#F3F6FA"


def read_results() -> list[dict[str, str]]:
    with RESULTS.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_box(
    ax: plt.Axes,
    x: float,
    title: str,
    detail: str,
    color: str,
) -> None:
    y, width, height = 0.31, 0.16, 0.47
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        linewidth=1.3,
        edgecolor=color,
        facecolor="white",
    )
    ax.add_patch(box)
    ax.text(
        x + width / 2,
        y + height * 0.64,
        title,
        ha="center",
        va="center",
        fontsize=10,
        weight="bold",
        color=color,
    )
    ax.text(
        x + width / 2,
        y + height * 0.30,
        detail,
        ha="center",
        va="center",
        fontsize=8,
        color="#344054",
    )


def pipeline_figure() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 2.15))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    boxes = [
        (0.01, "Input stream", "N bytes", BLUE),
        (0.215, "Block partition", "blocks of at most\nb bytes", TEAL),
        (0.42, "Seven candidates", "complete serialized\nrecords", ORANGE),
        (0.625, "Exact selection", "shortest record\nper block", RED),
        (0.83, "Final choice", "adaptive vs.\nraw stream", BLUE),
    ]
    for index, (x, title, detail, color) in enumerate(boxes):
        draw_box(ax, x, title, detail, color)
        if index < len(boxes) - 1:
            ax.add_patch(
                FancyArrowPatch(
                    (x + 0.168, 0.545),
                    (boxes[index + 1][0] - 0.008, 0.545),
                    arrowstyle="-|>",
                    mutation_scale=13,
                    linewidth=1.3,
                    color=GRAY,
                )
            )
    ax.text(
        0.5,
        0.08,
        "Framing, identifiers, lengths, payloads, and byte alignment are included.",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#344054",
    )
    save(fig, "codec_pipeline")


def mode_figure() -> None:
    fig, axes = plt.subplots(2, 4, figsize=(10.2, 4.0))
    axes = axes.ravel()
    modes = [
        ("Raw", "7A 00 12 4F", "literal bytes", BLUE),
        ("Zero block", "00 00 00 00", "length only", TEAL),
        ("Boundary trim", "00 00 7A 12 00", "lead + middle + trail", ORANGE),
        ("One gaps", "00100100", "positions 2, 5", RED),
        ("Zero gaps", "11101111", "zero position 3", GRAY),
        ("One runs", "0011100110", "runs [2,5), [7,9)", BLUE),
        ("Nonzero bytes", "00 7A 00 12", "(1,7A), (3,12)", TEAL),
    ]
    for ax, (title, pattern, payload, color) in zip(axes, modes):
        ax.axis("off")
        ax.add_patch(
            FancyBboxPatch(
                (0.02, 0.08),
                0.96,
                0.84,
                boxstyle="round,pad=0.025,rounding_size=0.04",
                linewidth=1.4,
                edgecolor=color,
                facecolor=LIGHT,
                transform=ax.transAxes,
            )
        )
        ax.text(
            0.5,
            0.73,
            title,
            ha="center",
            va="center",
            fontsize=10,
            weight="bold",
            color=color,
            transform=ax.transAxes,
        )
        ax.text(
            0.5,
            0.49,
            pattern,
            ha="center",
            va="center",
            fontsize=10,
            family="monospace",
            transform=ax.transAxes,
        )
        ax.text(
            0.5,
            0.25,
            payload,
            ha="center",
            va="center",
            fontsize=8.5,
            color="#344054",
            transform=ax.transAxes,
        )
    axes[-1].axis("off")
    axes[-1].text(
        0.5,
        0.62,
        "Raw fallback",
        ha="center",
        va="center",
        fontsize=11,
        weight="bold",
        color=RED,
        transform=axes[-1].transAxes,
    )
    axes[-1].text(
        0.5,
        0.38,
        "protects blocks where no\nstructural mode is shorter",
        ha="center",
        va="center",
        fontsize=9,
        color="#344054",
        transform=axes[-1].transAxes,
    )
    fig.subplots_adjust(wspace=0.16, hspace=0.18)
    save(fig, "mode_examples")


def ratio_figure(rows: list[dict[str, str]]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["method"])].append(row)
    datasets = [
        ("SuiteSparse_HB_bcsstk_confirmation", "SuiteSparse"),
        ("kmnist_confirmation", "KMNIST"),
    ]
    methods = [
        ("legacy_oracle", "Five-mode\npredecessor", GRAY),
        ("best_fixed", "Best fixed\nextended mode", ORANGE),
        ("extended_oracle", "Exact seven-mode\nselector", BLUE),
        ("domain_baseline", "Domain\nbaseline", TEAL),
    ]
    values: dict[str, list[float]] = {method[0]: [] for method in methods}
    for dataset, _ in datasets:
        originals = sum(
            int(row["original_bytes"])
            for row in grouped[(dataset, "extended_oracle")]
        )
        for method in ("legacy_oracle", "extended_oracle"):
            values[method].append(
                sum(
                    int(row["encoded_bytes"])
                    for row in grouped[(dataset, method)]
                )
                / originals
            )
        fixed_names = {
            method
            for current_dataset, method in grouped
            if current_dataset == dataset and method.startswith("fixed_")
        }
        values["best_fixed"].append(
            min(
                sum(
                    int(row["encoded_bytes"])
                    for row in grouped[(dataset, method)]
                )
                / originals
                for method in fixed_names
            )
        )
        baseline = (
            "sparse_position_gaps"
            if dataset == "SuiteSparse_HB_bcsstk_confirmation"
            else "png_per_image"
        )
        values["domain_baseline"].append(
            sum(
                int(row["encoded_bytes"])
                for row in grouped[(dataset, baseline)]
            )
            / originals
        )
    fig, ax = plt.subplots(figsize=(7.6, 3.7))
    width = 0.19
    offsets = (-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width)
    for offset, (key, label, color) in zip(offsets, methods):
        bars = ax.bar(
            [position + offset for position in range(2)],
            values[key],
            width=width,
            label=label,
            color=color,
        )
        for bar, value in zip(bars, values[key]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.018,
                f"{value:.4f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
            )
    ax.axhline(1.0, color="#98A2B3", linewidth=1, linestyle="--")
    ax.text(1.48, 1.01, "raw size", ha="right", va="bottom", fontsize=8, color=GRAY)
    ax.set_ylabel("Complete serialized ratio")
    ax.set_xticks([0, 1], [label for _, label in datasets])
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    save(fig, "Figure_3")


def mode_mix_figure(rows: list[dict[str, str]]) -> None:
    columns = [
        ("blocks_raw", "Raw", GRAY),
        ("blocks_zero", "Zero", "#8EC5FF"),
        ("blocks_zero_trim", "Boundary trim", ORANGE),
        ("blocks_one_gaps", "One gaps", RED),
        ("blocks_zero_gaps", "Zero gaps", "#8E6BBE"),
        ("blocks_one_runs", "One runs", BLUE),
        ("blocks_nonzero_bytes", "Nonzero bytes", TEAL),
    ]
    datasets = [
        ("SuiteSparse_HB_bcsstk_confirmation", "SuiteSparse"),
        ("kmnist_confirmation", "KMNIST"),
    ]
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if row["method"] == "extended_oracle":
            for column, _, _ in columns:
                counts[row["dataset"]][column] += int(row[column])
    fig, ax = plt.subplots(figsize=(7.7, 3.25))
    left = [0.0, 0.0]
    for column, label, color in columns:
        percentages = []
        for dataset, _ in datasets:
            total = sum(counts[dataset].values())
            percentages.append(100 * counts[dataset][column] / total)
        ax.barh([0, 1], percentages, left=left, height=0.52, label=label, color=color)
        for index, value in enumerate(percentages):
            if value >= 7:
                ax.text(
                    left[index] + value / 2,
                    index,
                    f"{value:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if color in {BLUE, TEAL, RED, GRAY} else "#1D2939",
                    weight="bold",
                )
        left = [current + value for current, value in zip(left, percentages)]
    ax.set_yticks([0, 1], [label for _, label in datasets])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of blocks selected by the exact seven-mode encoder")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.18)
    ax.legend(frameon=False, ncols=4, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    save(fig, "Figure_4")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = read_results()
    ratio_figure(rows)
    mode_mix_figure(rows)
    print("Generated manuscript figures")


if __name__ == "__main__":
    main()
