from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT.parent / "paper"
TABLES = PAPER / "tables"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def grouped_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["dataset"], row["method"])].append(row)
    output = []
    for (dataset, method), items in sorted(groups.items()):
        original = sum(int(row["original_bytes"]) for row in items)
        encoded = sum(int(row["encoded_bytes"]) for row in items)
        output.append(
            {
                "dataset": dataset,
                "method": method,
                "files": len(items),
                "original": original,
                "encoded": encoded,
                "ratio": encoded / original,
            }
        )
    return output


def latex_escape(value: str) -> str:
    return value.replace("_", r"\_")


def write_confirmation_table(rows: list[dict[str, str]]) -> None:
    summary = grouped_summary(rows)
    by_dataset = defaultdict(dict)
    for row in summary:
        by_dataset[row["dataset"]][row["method"]] = row
    labels = {
        "SuiteSparse_HB_bcsstk_confirmation": "SuiteSparse bcsstk10--12",
        "kmnist_confirmation": "KMNIST test",
    }
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Complete serialized ratios on confirmation files.}",
        r"\label{tab:confirmation}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Dataset & Files & Legacy & Extended & Best fixed & Domain baseline \\",
        r"\midrule",
    ]
    for dataset, methods in by_dataset.items():
        best_fixed = min(
            row["ratio"]
            for method, row in methods.items()
            if method.startswith("fixed_")
        )
        baseline_name = (
            "sparse_position_gaps"
            if "SuiteSparse" in dataset
            else "png_per_image"
        )
        lines.append(
            f"{labels[dataset]} & {methods['extended_oracle']['files']} & "
            f"{methods['legacy_oracle']['ratio']:.4f} & "
            f"\\textbf{{{methods['extended_oracle']['ratio']:.4f}}} & "
            f"{best_fixed:.4f} & {methods[baseline_name]['ratio']:.4f} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.92\textwidth}",
        r"\footnotesize\textit{Note.} Lower ratios are better. The SuiteSparse row aggregates \texttt{bcsstk10.smb}, \texttt{bcsstk11.smb}, and \texttt{bcsstk12.smb}. The domain baseline is global position gaps for SuiteSparse and PNG for KMNIST.",
        r"\end{minipage}",
        r"\end{table*}",
        "",
    ]
    (TABLES / "confirmation.tex").write_text("\n".join(lines), encoding="utf-8")


def write_file_table(rows: list[dict[str, str]]) -> None:
    lookup = defaultdict(dict)
    for row in rows:
        lookup[(row["dataset"], row["file"])][row["method"]] = row
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Per-file confirmation ratios.}",
        r"\label{tab:per-file}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"File & Original bytes & Extended & Best fixed & Domain baseline \\",
        r"\midrule",
    ]
    for (_, file_name), methods in sorted(lookup.items()):
        extended = methods["extended_oracle"]
        best_fixed = min(
            float(row["ratio"])
            for method, row in methods.items()
            if method.startswith("fixed_")
        )
        baseline_name = (
            "sparse_position_gaps"
            if "sparse_position_gaps" in methods
            else "png_per_image"
        )
        lines.append(
            f"{latex_escape(file_name)} & {int(extended['original_bytes']):,} & "
            f"{float(extended['ratio']):.4f} & {best_fixed:.4f} & "
            f"{float(methods[baseline_name]['ratio']):.4f} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.92\textwidth}",
        r"\footnotesize\textit{Note.} The domain baseline is global position gaps for matrix bitmaps and PNG for image tensors.",
        r"\end{minipage}",
        r"\end{table*}",
        "",
    ]
    (TABLES / "per_file.tex").write_text("\n".join(lines), encoding="utf-8")


def write_statistics(rows: list[dict[str, str]]) -> None:
    lookup = defaultdict(dict)
    for row in rows:
        lookup[(row["dataset"], row["file"])][row["method"]] = row
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Descriptive confirmation differences within ASBX.}",
        r"\label{tab:statistics}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Dataset & Files & Byte gain & Relative gain \\",
        r"\midrule",
    ]
    for dataset in sorted({key[0] for key in lookup}):
        file_records = [
            methods for (current, _), methods in lookup.items() if current == dataset
        ]
        fixed_methods = [
            method
            for method in file_records[0]
            if method.startswith("fixed_")
        ]
        best_method = min(
            fixed_methods,
            key=lambda method: sum(
                int(record[method]["encoded_bytes"]) for record in file_records
            ),
        )
        fixed = [int(record[best_method]["encoded_bytes"]) for record in file_records]
        extended = [
            int(record["extended_oracle"]["encoded_bytes"]) for record in file_records
        ]
        differences = [left - right for left, right in zip(fixed, extended)]
        gain = sum(differences)
        relative = gain / sum(fixed)
        label = (
            "SuiteSparse bcsstk10--12"
            if "SuiteSparse" in dataset
            else "KMNIST test"
        )
        lines.append(
            f"{label} & {len(file_records)} & {gain:,} & "
            f"{100 * relative:.2f}\\% \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.92\textwidth}",
        r"\footnotesize\textit{Note.} Byte gain is the aggregate saving over all files in the dataset. Differences compare the exact selector with the best fixed ASBX mode. No population-level significance test is claimed.",
        r"\end{minipage}",
        r"\end{table*}",
        "",
    ]
    (TABLES / "statistics.tex").write_text("\n".join(lines), encoding="utf-8")


def write_mode_counts(rows: list[dict[str, str]]) -> None:
    columns = [
        ("blocks_raw", "Raw"),
        ("blocks_zero", "Zero"),
        ("blocks_zero_trim", "Boundary trim"),
        ("blocks_one_gaps", "Set-bit gaps"),
        ("blocks_zero_gaps", "Zero-bit gaps"),
        ("blocks_one_runs", "Set-bit runs"),
        ("blocks_nonzero_bytes", "Nonzero bytes"),
    ]
    labels = {
        "SuiteSparse_HB_bcsstk_confirmation": "SuiteSparse",
        "kmnist_confirmation": "KMNIST",
    }
    counts = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if row["method"] != "extended_oracle":
            continue
        for column, _ in columns:
            counts[row["dataset"]][column] += int(row[column])
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Complete block-mode counts on confirmation corpora.}",
        r"\label{tab:mode-counts}",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Mode & SuiteSparse & KMNIST \\",
        r"\midrule",
    ]
    for column, label in columns:
        lines.append(
            f"{label} & "
            f"{counts['SuiteSparse_HB_bcsstk_confirmation'][column]:,} & "
            f"{counts['kmnist_confirmation'][column]:,} \\\\"
        )
    totals = {
        dataset: sum(values.values()) for dataset, values in counts.items()
    }
    lines += [
        r"\midrule",
        f"Total & {totals['SuiteSparse_HB_bcsstk_confirmation']:,} & "
        f"{totals['kmnist_confirmation']:,} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.92\columnwidth}",
        r"\footnotesize\textit{Note.} Counts include every block encoded by the exact seven-mode selector; each corpus column therefore sums to its complete block count.",
        r"\end{minipage}",
        r"\end{table}",
        "",
    ]
    (TABLES / "mode_counts.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    confirmation = read(ROOT / "results" / "confirmation_domains.csv")
    write_confirmation_table(confirmation)
    write_file_table(confirmation)
    write_statistics(confirmation)
    write_mode_counts(confirmation)
    print("Generated manuscript tables")


if __name__ == "__main__":
    main()
