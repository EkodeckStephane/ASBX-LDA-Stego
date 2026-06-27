from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.domain_baselines import (  # noqa: E402
    decode_png_images,
    decode_sparse_positions,
    encode_png_images,
    encode_sparse_positions,
)

DATA = ROOT / "data" / "external" / "confirmation"
RESULTS = ROOT / "results" / "confirmation_domains.csv"
BASELINE_METHODS = {"png_per_image", "sparse_position_gaps"}


def read_rows() -> list[dict[str, str]]:
    with RESULTS.open(newline="", encoding="utf-8") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row["method"] not in BASELINE_METHODS
        ]


def baseline_rows(fieldnames: list[str]) -> list[dict[str, str]]:
    output = []
    datasets = (
        (
            "sparse_matrix_pattern",
            "SuiteSparse_HB_bcsstk_confirmation",
            DATA / "sparse_matrices",
            "sparse_position_gaps",
            encode_sparse_positions,
            decode_sparse_positions,
        ),
        (
            "grayscale_image_tensor",
            "kmnist_confirmation",
            DATA / "kmnist",
            "png_per_image",
            encode_png_images,
            decode_png_images,
        ),
    )
    block_fields = [name for name in fieldnames if name.startswith("blocks_")]
    for domain, dataset, directory, method, encode, decode in datasets:
        for path in sorted(directory.iterdir()):
            source = path.read_bytes()
            payload = encode(source)
            if decode(payload) != source:
                raise AssertionError(f"{method} round trip failed for {path}")
            row = {
                "domain": domain,
                "dataset": dataset,
                "file": path.name,
                "method": method,
                "original_bytes": str(len(source)),
                "encoded_bytes": str(len(payload)),
                "ratio": str(len(payload) / len(source)),
                **{name: "0" for name in block_fields},
            }
            output.append(row)
            print(f"Measured {dataset}/{path.name}: {method}", flush=True)
    return output


def main() -> None:
    rows = read_rows()
    fieldnames = list(rows[0])
    rows.extend(baseline_rows(fieldnames))
    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} confirmation measurements", flush=True)


if __name__ == "__main__":
    main()
