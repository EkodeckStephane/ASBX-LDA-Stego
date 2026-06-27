from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "08_ml_selector_verdict.md"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    files = read(RESULTS / "ml_selector_files.csv")
    models = {row["model"]: row for row in read(RESULTS / "ml_selector_models.csv")}
    timing = {row["method"]: row for row in read(RESULTS / "ml_feature_timing.csv")}
    grouped = defaultdict(list)
    for row in files:
        grouped[(row["model"], row["dataset"])].append(row)

    rows = []
    for (model, dataset), items in sorted(grouped.items()):
        original = sum(int(row["original_bytes"]) for row in items)
        oracle = sum(int(row["oracle_bytes"]) for row in items)
        deterministic = sum(int(row["deterministic_bytes"]) for row in items)
        selected = sum(int(row["selected_bytes"]) for row in items)
        size = int(models[model]["model_bytes"])
        rows.append(
            {
                "model": model,
                "dataset": dataset,
                "files": len(items),
                "original_bytes": original,
                "oracle_ratio": oracle / original,
                "deterministic_ratio": deterministic / original,
                "ml_ratio": selected / original,
                "gain_vs_deterministic_pct": 100
                * (deterministic - selected)
                / deterministic,
                "oracle_regret_pct": 100 * (selected - oracle) / oracle,
                "model_bytes": size,
                "ratio_with_model_charged_once": (selected + size) / original,
                "net_gain_bytes_after_model": deterministic - selected - size,
            }
        )

    output = RESULTS / "ml_selector_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# ML and Neural Selector Verdict",
        "",
        "The codec modes, serialization, and decoder are unchanged. Models only",
        "replace the encoder-side mode decision. Training uses real training",
        "files; evaluation uses the untouched real test files.",
        "",
        "| Model | Dataset | ML ratio | Gain vs rule | Regret vs oracle | Model bytes | Net bytes after charging model once |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['dataset']} | "
            f"{float(row['ml_ratio']):.6f} | "
            f"{float(row['gain_vs_deterministic_pct']):.3f}% | "
            f"{float(row['oracle_regret_pct']):.3f}% | "
            f"{row['model_bytes']} | {row['net_gain_bytes_after_model']} |"
        )

    lines += [
        "",
        "## Runtime",
        "",
        f"- Deterministic features: "
        f"{float(timing['deterministic_features']['microseconds_per_block']):.1f} us/block.",
        f"- ML features: "
        f"{float(timing['ml_features']['microseconds_per_block']):.1f} us/block.",
    ]
    for model, row in models.items():
        lines.append(
            f"- `{model}` prediction only: "
            f"{1e6 * float(row['test_inference_seconds']) / int(row['test_blocks']):.2f} us/block."
        )

    lines += [
        "",
        "## Decision",
        "",
        "The small decision tree is the practical ML candidate. It captures most",
        "of the available improvement with an 8 kB model and negligible",
        "prediction time. Histogram gradient boosting is closest to the oracle",
        "but its 453 kB model is not justified for these corpus sizes. The small",
        "neural network is larger and less accurate than the tree, so deeper",
        "learning is not justified by the current evidence.",
        "",
        "ML improves mode selection but does not change the broader codec verdict:",
        "general-purpose codecs remain much smaller on these datasets. ML should",
        "remain an optional encoder-side selector, not the central compression",
        "claim.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote ML selector verdict to {REPORT}")


if __name__ == "__main__":
    main()

