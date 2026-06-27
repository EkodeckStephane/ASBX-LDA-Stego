from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "05_real_corpus_verdict.md"


def main() -> None:
    with (RESULTS / "real_corpus_measurements.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["corpus"], row["method"])].append(row)

    summary = []
    for (corpus, method), items in sorted(grouped.items()):
        original = sum(int(row["original_bytes"]) for row in items)
        encoded = sum(int(row["encoded_bytes"]) for row in items)
        summary.append(
            {
                "corpus": corpus,
                "method": method,
                "files": len(items),
                "original_bytes": original,
                "encoded_bytes": encoded,
                "weighted_ratio": encoded / original,
            }
        )

    output = RESULTS / "real_corpus_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    lines = [
        "# Preliminary Verdict on Real Files",
        "",
        "This evaluation uses complete Canterbury files and the fixed 64 KiB",
        "prefixes of all Silesia files. The inputs are real public-corpus files,",
        "not generated data. Silesia prefixes remain exploratory; complete",
        "Silesia evaluation is still required.",
        "",
        "| Corpus | Method | Files | Weighted ratio |",
        "|---|---|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['corpus']} | {row['method']} | {row['files']} | "
            f"{float(row['weighted_ratio']):.6f} |"
        )

    by_corpus = defaultdict(dict)
    for row in summary:
        by_corpus[row["corpus"]][row["method"]] = float(row["weighted_ratio"])

    lines += ["", "## Verdict", ""]
    for corpus, methods in sorted(by_corpus.items()):
        oracle = methods["asbx_oracle"]
        selector = methods["asbx_deterministic"]
        fixed = min(
            value
            for method, value in methods.items()
            if method.startswith("asbx_fixed_")
        )
        modern = min(methods[name] for name in ("zlib_9", "bzip2_9", "lzma_9"))
        lines.append(
            f"- `{corpus}`: oracle `{oracle:.6f}`, selector `{selector:.6f}`, "
            f"best fixed ASBX `{fixed:.6f}`, best tested general codec "
            f"`{modern:.6f}`."
        )
    lines += [
        "",
        "The project has not yet met its continuation criterion. These general",
        "corpora are controls rather than the target sparse application domains.",
        "A positive article claim requires at least two real sparse-domain",
        "datasets and held-out file-level validation. The current result can",
        "support only a preliminary engineering verdict.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote real-corpus summary and verdict to {REPORT}")


if __name__ == "__main__":
    main()

