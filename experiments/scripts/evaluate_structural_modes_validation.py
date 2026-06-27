from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import candidates, fixed_candidate  # noqa: E402
from asbc.modes import Mode  # noqa: E402
from asbc.varint import encode_uvarint  # noqa: E402

DATA = ROOT / "data" / "external"
RESULTS = ROOT / "results"
BLOCK_SIZE = 256
LEGACY_MODES = {
    Mode.RAW,
    Mode.ZERO,
    Mode.ZERO_TRIM,
    Mode.ONE_GAPS,
    Mode.ZERO_GAPS,
}


def validation_files():
    for path in sorted((DATA / "sparse_matrices" / "validation").glob("*.smb")):
        yield "sparse_matrix_pattern", "SuiteSparse_HB_bcsstk", path
    for dataset in ("mnist", "fashion_mnist"):
        files = sorted((DATA / "image_tensors" / dataset / "train").glob("*.img"))
        for path in files[-12:]:
            yield "grayscale_image_tensor", dataset, path


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
    methods = [
        "legacy_oracle",
        "extended_oracle",
        *[f"fixed_{mode.name.lower()}" for mode in Mode],
    ]
    for domain, dataset, path in validation_files():
        source = path.read_bytes()
        record_sizes = {method: [] for method in methods}
        mode_counts = {mode: 0 for mode in Mode}
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
            record_sizes["legacy_oracle"].append(legacy.serialized_bytes)
            record_sizes["extended_oracle"].append(extended.serialized_bytes)
            mode_counts[extended.mode] += 1
            for mode in Mode:
                record_sizes[f"fixed_{mode.name.lower()}"].append(
                    fixed_candidate(block, mode).serialized_bytes
                )
        for method in methods:
            encoded = stream_size(len(source), record_sizes[method])
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
                        f"extended_blocks_{mode.name.lower()}": mode_counts[mode]
                        for mode in Mode
                    },
                }
            )

    output = RESULTS / "structural_modes_validation.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} structural-mode validation measurements")


if __name__ == "__main__":
    main()

