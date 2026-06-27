from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "07_sparse_domain_verdict.md"


def main() -> None:
    with (RESULTS / "sparse_domain_measurements.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))

    groups = defaultdict(list)
    for row in rows:
        groups[(row["domain"], row["dataset"], row["method"])].append(row)
    summary = []
    for (domain, dataset, method), items in sorted(groups.items()):
        original = sum(int(row["original_bytes"]) for row in items)
        encoded = sum(int(row["encoded_bytes"]) for row in items)
        summary.append(
            {
                "domain": domain,
                "dataset": dataset,
                "method": method,
                "files": len(items),
                "original_bytes": original,
                "encoded_bytes": encoded,
                "weighted_ratio": encoded / original,
            }
        )

    output = RESULTS / "sparse_domain_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    lines = [
        "# Verdict on Real Sparse Domains",
        "",
        "All rows use held-out source test partitions. The ASBX selector was frozen",
        "before these files were prepared or measured.",
        "",
        "| Domain | Dataset | Method | Files | Weighted ratio |",
        "|---|---|---|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['domain']} | {row['dataset']} | {row['method']} | "
            f"{row['files']} | {float(row['weighted_ratio']):.6f} |"
        )

    lines += ["", "## Decision evidence", ""]
    datasets = defaultdict(dict)
    for row in summary:
        datasets[(row["domain"], row["dataset"])][row["method"]] = float(
            row["weighted_ratio"]
        )
    for (domain, dataset), methods in sorted(datasets.items()):
        selector = methods["asbx_deterministic"]
        oracle = methods["asbx_oracle"]
        fixed = min(
            value
            for method, value in methods.items()
            if method.startswith("asbx_fixed_")
        )
        competitor = min(
            value
            for method, value in methods.items()
            if not method.startswith("asbx_")
        )
        lines.append(
            f"- `{dataset}`: selector `{selector:.6f}`, oracle `{oracle:.6f}`, "
            f"best fixed ASBX `{fixed:.6f}`, best external baseline "
            f"`{competitor:.6f}`."
        )
    lines += [
        "",
        "A continuation decision requires the adaptive selector to improve the",
        "best fixed component on a real domain after complete costs. Competitive",
        "positioning also requires comparison with the specialized baseline;",
        "beating raw storage alone is insufficient.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote sparse-domain verdict to {REPORT}")


if __name__ == "__main__":
    main()

