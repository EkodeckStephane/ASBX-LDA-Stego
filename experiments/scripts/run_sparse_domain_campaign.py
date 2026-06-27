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

from asbc.codec import decode, encode, encode_fixed, encode_with_selector  # noqa: E402
from asbc.domain_baselines import (  # noqa: E402
    decode_png_images,
    decode_sparse_positions,
    encode_png_images,
    encode_sparse_positions,
)
from asbc.modes import Mode  # noqa: E402
from asbc.selector import deterministic_candidate  # noqa: E402

DATA = ROOT / "data" / "external"
RESULTS = ROOT / "results"
BLOCK_SIZE = 256


def measured(method, data: bytes) -> tuple[bytes, float]:
    started = time.perf_counter()
    payload = method(data)
    return payload, time.perf_counter() - started


def iter_test_files():
    for path in sorted((DATA / "sparse_matrices" / "test").glob("*.smb")):
        yield "sparse_matrix_pattern", "SuiteSparse_HB_bcsstk", path
    for dataset in ("mnist", "fashion_mnist"):
        for path in sorted(
            (DATA / "image_tensors" / dataset / "test").glob("*.img")
        ):
            yield "grayscale_image_tensor", dataset, path


def main() -> None:
    rows = []
    asbx_methods = {
        "asbx_oracle": lambda data: encode(data, BLOCK_SIZE),
        "asbx_deterministic": lambda data: encode_with_selector(
            data, BLOCK_SIZE, deterministic_candidate
        ),
        **{
            f"asbx_fixed_{mode.name.lower()}": (
                lambda data, selected=mode: encode_fixed(data, selected, BLOCK_SIZE)
            )
            for mode in Mode
        },
    }
    generic = {
        "zlib_9": lambda data: zlib.compress(data, 9),
        "bzip2_9": lambda data: bz2.compress(data, compresslevel=9),
        "lzma_9": lambda data: lzma.compress(data, preset=9),
    }

    for domain, dataset, path in iter_test_files():
        source = path.read_bytes()
        methods = {**asbx_methods, **generic}
        if domain == "sparse_matrix_pattern":
            methods["sparse_position_gaps"] = encode_sparse_positions
        else:
            methods["png_per_image"] = encode_png_images
        for method_name, method in methods.items():
            payload, seconds = measured(method, source)
            if method_name.startswith("asbx_") and decode(payload) != source:
                raise RuntimeError(f"ASBX round-trip mismatch: {path}/{method_name}")
            if (
                method_name == "sparse_position_gaps"
                and decode_sparse_positions(payload) != source
            ):
                raise RuntimeError(f"sparse baseline mismatch: {path}")
            if method_name == "png_per_image" and decode_png_images(payload) != source:
                raise RuntimeError(f"PNG baseline mismatch: {path}")
            rows.append(
                {
                    "domain": domain,
                    "dataset": dataset,
                    "split": "test",
                    "file": path.name,
                    "method": method_name,
                    "original_bytes": len(source),
                    "encoded_bytes": len(payload),
                    "ratio": len(payload) / len(source),
                    "encode_seconds": seconds,
                }
            )
        print(f"Measured {domain}/{dataset}/{path.name}")

    output = RESULTS / "sparse_domain_measurements.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} sparse-domain measurements")


if __name__ == "__main__":
    main()
