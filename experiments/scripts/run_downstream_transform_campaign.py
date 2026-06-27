from __future__ import annotations

import bz2
import csv
import lzma
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import decode, encode, encode_with_selector  # noqa: E402
from asbc.selector import deterministic_candidate  # noqa: E402

DATA = ROOT / "data" / "external"
RESULTS = ROOT / "results"
BLOCK_SIZE = 256

CODECS = {
    "zlib_9": (
        lambda data: zlib.compress(data, 9),
        zlib.decompress,
    ),
    "bzip2_9": (
        lambda data: bz2.compress(data, compresslevel=9),
        bz2.decompress,
    ),
    "lzma_9": (
        lambda data: lzma.compress(data, preset=9),
        lzma.decompress,
    ),
}


def iter_test_files():
    for path in sorted((DATA / "sparse_matrices" / "test").glob("*.smb")):
        yield "sparse_matrix_pattern", "SuiteSparse_HB_bcsstk", path
    for dataset in ("mnist", "fashion_mnist"):
        for path in sorted(
            (DATA / "image_tensors" / dataset / "test").glob("*.img")
        ):
            yield "grayscale_image_tensor", dataset, path


def timed(function, data: bytes) -> tuple[bytes, float]:
    started = time.perf_counter()
    output = function(data)
    return output, time.perf_counter() - started


def main() -> None:
    rows = []
    transforms = {
        "raw": lambda data: data,
        "asbx_deterministic": lambda data: encode_with_selector(
            data, BLOCK_SIZE, deterministic_candidate
        ),
        "asbx_oracle": lambda data: encode(data, BLOCK_SIZE),
    }

    for domain, dataset, path in iter_test_files():
        source = path.read_bytes()
        for transform_name, transform in transforms.items():
            transformed, transform_seconds = timed(transform, source)
            if transform_name.startswith("asbx_") and decode(transformed) != source:
                raise RuntimeError(f"transform round-trip mismatch: {path}")
            for codec_name, (compress, decompress) in CODECS.items():
                compressed, downstream_seconds = timed(compress, transformed)
                restored_transform, downstream_decode_seconds = timed(
                    decompress, compressed
                )
                if restored_transform != transformed:
                    raise RuntimeError(
                        f"downstream round-trip mismatch: {path}/{codec_name}"
                    )
                started = time.perf_counter()
                restored = (
                    decode(restored_transform)
                    if transform_name.startswith("asbx_")
                    else restored_transform
                )
                transform_decode_seconds = time.perf_counter() - started
                if restored != source:
                    raise RuntimeError(
                        f"pipeline round-trip mismatch: "
                        f"{path}/{transform_name}/{codec_name}"
                    )
                rows.append(
                    {
                        "domain": domain,
                        "dataset": dataset,
                        "file": path.name,
                        "transform": transform_name,
                        "downstream_codec": codec_name,
                        "original_bytes": len(source),
                        "transform_bytes": len(transformed),
                        "final_bytes": len(compressed),
                        "final_ratio": len(compressed) / len(source),
                        "transform_encode_seconds": transform_seconds,
                        "downstream_encode_seconds": downstream_seconds,
                        "downstream_decode_seconds": downstream_decode_seconds,
                        "transform_decode_seconds": transform_decode_seconds,
                    }
                )
        print(f"Measured downstream pipelines for {dataset}/{path.name}")

    output = RESULTS / "downstream_transform_measurements.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} downstream-transform measurements")


if __name__ == "__main__":
    main()

