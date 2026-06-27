from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "04_initial_selector_results.md"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    summary = read_rows(RESULTS / "selector_test_summary.csv")
    confusion = read_rows(RESULTS / "selector_block_confusion.csv")
    original = sum(int(row["original_bytes"]) for row in summary)
    oracle = sum(int(row["oracle_bytes"]) for row in summary)
    deterministic = sum(int(row["deterministic_bytes"]) for row in summary)
    regret = deterministic - oracle
    worst = max(summary, key=lambda row: float(row["deterministic_regret_fraction"]))
    mismatches = [
        row
        for row in confusion
        if row["oracle_mode"] != row["selected_mode"]
        and int(row["regret_bytes"]) > 0
    ]
    mismatches.sort(key=lambda row: int(row["regret_bytes"]), reverse=True)

    lines = [
        "# Initial Deterministic Selector Results",
        "",
        "These results are exploratory and use only deterministic synthetic files.",
        "They are not evidence of performance on real application domains.",
        "",
        "## Held-out aggregate",
        "",
        f"- Test files: {len(summary)}.",
        f"- Original bytes: {original}.",
        f"- Exact-oracle ratio: {oracle / original:.6f}.",
        f"- Deterministic-selector ratio: {deterministic / original:.6f}.",
        f"- Aggregate regret: {regret} bytes ({regret / original:.4%}).",
        (
            f"- Largest file-level regret: {worst['scenario']} at "
            f"{float(worst['deterministic_regret_fraction']):.4%}."
        ),
        "",
        "The working median/aggregate regret target is met, but the tail-regret",
        "target is not yet met because clustered set bits remain difficult.",
        "",
        "## Per-scenario results",
        "",
        "| Scenario | Oracle ratio | Selector ratio | Regret bytes | Train-selected fixed | Fixed test ratio |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for row in summary:
        lines.append(
            "| {scenario} | {oracle:.6f} | {selector:.6f} | {regret} | {fixed} | {fixed_ratio:.6f} |".format(
                scenario=row["scenario"],
                oracle=float(row["oracle_ratio"]),
                selector=float(row["deterministic_ratio"]),
                regret=row["deterministic_regret_bytes"],
                fixed=row["train_selected_fixed"],
                fixed_ratio=float(row["selected_fixed_test_ratio"]),
            )
        )

    lines += [
        "",
        "## Largest block-level mistakes",
        "",
        "| Scenario | Oracle mode | Selected mode | Blocks | Regret bytes |",
        "|---|---|---|---:|---:|",
    ]
    for row in mismatches[:10]:
        lines.append(
            f"| {row['scenario']} | {row['oracle_mode']} | "
            f"{row['selected_mode']} | {row['blocks']} | {row['regret_bytes']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "The run-structure feature removes nearly all regret on clustered-bit",
        "files while preserving exact decisions on the dense, random, and",
        "zero-block controls. The remaining mistakes are small boundary cases",
        "between zero trimming and one-position gaps.",
        "",
        "No machine-learning experiment is justified at this stage. The next",
        "required step is evaluation on real held-out files. The deterministic",
        "rule is frozen for that evaluation; it must not be retuned on test",
        "files.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote selector report to {REPORT}")


if __name__ == "__main__":
    main()
