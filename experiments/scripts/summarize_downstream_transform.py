from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "09_downstream_transform_verdict.md"


def main() -> None:
    with (RESULTS / "downstream_transform_measurements.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))

    grouped = defaultdict(list)
    lookup = {}
    for row in rows:
        grouped[
            (row["domain"], row["dataset"], row["downstream_codec"], row["transform"])
        ].append(row)
        lookup[
            (
                row["domain"],
                row["dataset"],
                row["file"],
                row["downstream_codec"],
                row["transform"],
            )
        ] = row

    summary = []
    datasets = sorted({(row["domain"], row["dataset"]) for row in rows})
    codecs = sorted({row["downstream_codec"] for row in rows})
    transforms = sorted({row["transform"] for row in rows})
    for domain, dataset in datasets:
        files = sorted(
            {
                row["file"]
                for row in rows
                if row["domain"] == domain and row["dataset"] == dataset
            }
        )
        for codec in codecs:
            raw_sizes = np.asarray(
                [
                    int(lookup[(domain, dataset, file, codec, "raw")]["final_bytes"])
                    for file in files
                ],
                dtype=np.int64,
            )
            for transform in transforms:
                items = grouped[(domain, dataset, codec, transform)]
                original = sum(int(row["original_bytes"]) for row in items)
                final = sum(int(row["final_bytes"]) for row in items)
                candidate_sizes = np.asarray(
                    [
                        int(
                            lookup[
                                (domain, dataset, file, codec, transform)
                            ]["final_bytes"]
                        )
                        for file in files
                    ],
                    dtype=np.int64,
                )
                differences = raw_sizes - candidate_sizes
                if transform == "raw" or np.all(differences == 0):
                    p_value = 1.0
                else:
                    try:
                        p_value = float(
                            wilcoxon(
                                differences,
                                alternative="greater",
                                zero_method="wilcox",
                            ).pvalue
                        )
                    except ValueError:
                        p_value = 1.0
                summary.append(
                    {
                        "domain": domain,
                        "dataset": dataset,
                        "downstream_codec": codec,
                        "transform": transform,
                        "files": len(files),
                        "original_bytes": original,
                        "final_bytes": final,
                        "weighted_ratio": final / original,
                        "difference_vs_raw_bytes": int(differences.sum()),
                        "wins_vs_raw": int(np.sum(differences > 0)),
                        "ties_vs_raw": int(np.sum(differences == 0)),
                        "losses_vs_raw": int(np.sum(differences < 0)),
                        "one_sided_wilcoxon_p": p_value,
                        "total_encode_seconds": sum(
                            float(row["transform_encode_seconds"])
                            + float(row["downstream_encode_seconds"])
                            for row in items
                        ),
                        "total_decode_seconds": sum(
                            float(row["downstream_decode_seconds"])
                            + float(row["transform_decode_seconds"])
                            for row in items
                        ),
                    }
                )

    output = RESULTS / "downstream_transform_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    lines = [
        "# Downstream Transform Verdict",
        "",
        "Each comparison uses the same downstream codec and held-out real files.",
        "Every pipeline was decoded back to the exact original bytes.",
        "",
        "| Dataset | Codec | Transform | Ratio | Difference vs raw codec | W/T/L | One-sided p |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['dataset']} | {row['downstream_codec']} | "
            f"{row['transform']} | {float(row['weighted_ratio']):.6f} | "
            f"{row['difference_vs_raw_bytes']} | "
            f"{row['wins_vs_raw']}/{row['ties_vs_raw']}/{row['losses_vs_raw']} | "
            f"{float(row['one_sided_wilcoxon_p']):.6g} |"
        )

    transformed = [row for row in summary if row["transform"] != "raw"]
    positive = [row for row in transformed if int(row["difference_vs_raw_bytes"]) > 0]
    lines += ["", "## Decision", ""]
    if positive:
        best = max(positive, key=lambda row: int(row["difference_vs_raw_bytes"]))
        lines.append(
            "At least one transform-plus-codec pipeline improves its raw-codec "
            "counterpart in aggregate."
        )
        lines.append(
            f"The largest byte improvement is `{best['dataset']}` with "
            f"`{best['transform']} -> {best['downstream_codec']}`: "
            f"{best['difference_vs_raw_bytes']} bytes."
        )
        lines.append(
            "Continuation requires that the gain also be consistent by file, "
            "statistically supported, and practically large enough to justify "
            "the transform runtime."
        )
    else:
        lines.append(
            "Neither the practical selector nor the exact oracle improves any "
            "tested downstream codec in aggregate. This rejects the current "
            "ASBX representation as a useful upstream transform."
        )
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote downstream-transform verdict to {REPORT}")


if __name__ == "__main__":
    main()

