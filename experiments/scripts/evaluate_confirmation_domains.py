from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import candidates, fixed_candidate  # noqa: E402
from asbc.domain_baselines import (  # noqa: E402
    decode_png_images,
    decode_sparse_positions,
    encode_png_images,
    encode_sparse_positions,
)
from asbc.modes import Mode  # noqa: E402
from asbc.varint import encode_uvarint  # noqa: E402

DATA = ROOT / "data" / "external" / "confirmation"
RESULTS = ROOT / "results"
BLOCK_SIZE = 256
LEGACY_MODES = set(list(Mode)[:5])


def files():
    for path in sorted((DATA / "sparse_matrices").glob("*.smb")):
        yield "sparse_matrix_pattern", "SuiteSparse_HB_bcsstk_confirmation", path
    for path in sorted((DATA / "kmnist").glob("*.img")):
        yield "grayscale_image_tensor", "kmnist_confirmation", path


def stream_size(original: int, records: list[int]) -> int:
    raw = 6 + len(encode_uvarint(original)) + original
    adaptive = (
        6
        + len(encode_uvarint(original))
        + len(encode_uvarint(BLOCK_SIZE))
        + len(encode_uvarint(len(records)))
        + sum(records)
    )
    return min(raw, adaptive)


def main() -> None:
    rows = []
    for domain, dataset, path in files():
        source = path.read_bytes()
        records = {
            "legacy_oracle": [],
            "extended_oracle": [],
            **{f"fixed_{mode.name.lower()}": [] for mode in Mode},
        }
        counts = {mode: 0 for mode in Mode}
        for start in range(0, len(source), BLOCK_SIZE):
            block = source[start : start + BLOCK_SIZE]
            options = candidates(block)
            legacy = min(
                (item for item in options if item.mode in LEGACY_MODES),
                key=lambda item: (item.serialized_bytes, int(item.mode)),
            )
            extended = min(
                options, key=lambda item: (item.serialized_bytes, int(item.mode))
            )
            records["legacy_oracle"].append(legacy.serialized_bytes)
            records["extended_oracle"].append(extended.serialized_bytes)
            counts[extended.mode] += 1
            for mode in Mode:
                records[f"fixed_{mode.name.lower()}"].append(
                    fixed_candidate(block, mode).serialized_bytes
                )
        for method, sizes in records.items():
            encoded = stream_size(len(source), sizes)
            rows.append(
                {
                    "domain": domain,
                    "dataset": dataset,
                    "file": path.name,
                    "method": method,
                    "original_bytes": len(source),
                    "encoded_bytes": encoded,
                    "ratio": encoded / len(source),
                    **{
                        f"blocks_{mode.name.lower()}": counts[mode]
                        for mode in Mode
                    },
                }
            )
        if domain == "sparse_matrix_pattern":
            baseline_method = "sparse_position_gaps"
            baseline_payload = encode_sparse_positions(source)
            if decode_sparse_positions(baseline_payload) != source:
                raise AssertionError(f"{baseline_method} round trip failed for {path}")
        else:
            baseline_method = "png_per_image"
            baseline_payload = encode_png_images(source)
            if decode_png_images(baseline_payload) != source:
                raise AssertionError(f"{baseline_method} round trip failed for {path}")
        rows.append(
            {
                "domain": domain,
                "dataset": dataset,
                "file": path.name,
                "method": baseline_method,
                "original_bytes": len(source),
                "encoded_bytes": len(baseline_payload),
                "ratio": len(baseline_payload) / len(source),
                **{f"blocks_{mode.name.lower()}": counts[mode] for mode in Mode},
            }
        )
        print(f"Confirmed {dataset}/{path.name}")
    output = RESULTS / "confirmation_domains.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} untouched confirmation measurements")


if __name__ == "__main__":
    main()
