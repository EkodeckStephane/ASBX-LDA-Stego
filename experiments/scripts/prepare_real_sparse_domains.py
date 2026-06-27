from __future__ import annotations

import csv
import gzip
import hashlib
import struct
import tarfile
from pathlib import Path

import numpy as np
from scipy.io import mmread

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / "data" / "downloads"
OUTPUT = ROOT / "data" / "external"
MANIFEST = ROOT / "manifests" / "sparse_domains.csv"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_extract_member(archive: tarfile.TarFile, suffix: str) -> bytes:
    matches = [
        member
        for member in archive.getmembers()
        if member.isfile() and member.name.lower().endswith(suffix)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {suffix} member, found {len(matches)}")
    handle = archive.extractfile(matches[0])
    if handle is None:
        raise ValueError("unable to read archive member")
    return handle.read()


def matrix_bitmap(matrix_bytes: bytes) -> tuple[bytes, int, int, int]:
    temporary = ROOT / "data" / "downloads" / "_matrix.mtx"
    temporary.write_bytes(matrix_bytes)
    try:
        matrix = mmread(temporary).tocoo()
    finally:
        temporary.unlink(missing_ok=True)
    rows, cols = matrix.shape
    coordinates = np.unique(
        matrix.row.astype(np.int64) * cols + matrix.col.astype(np.int64)
    )
    bitmap = bytearray((rows * cols + 7) // 8)
    for position in coordinates:
        byte_index, bit_index = divmod(int(position), 8)
        bitmap[byte_index] |= 1 << (7 - bit_index)
    header = b"SMB1" + struct.pack(">QQQ", rows, cols, len(coordinates))
    return header + bytes(bitmap), rows, cols, len(coordinates)


def prepare_matrices(rows: list[dict[str, object]]) -> None:
    destination = OUTPUT / "sparse_matrices"
    destination.mkdir(parents=True, exist_ok=True)
    split_by_index = {
        1: "train",
        2: "train",
        3: "train",
        4: "validation",
        5: "validation",
        6: "validation",
        7: "test",
        8: "test",
        9: "test",
    }
    for index in range(1, 10):
        name = f"bcsstk{index:02d}"
        archive_path = DOWNLOADS / "suitesparse" / f"{name}.tar.gz"
        archive_bytes = archive_path.read_bytes()
        with tarfile.open(archive_path, "r:gz") as archive:
            source = safe_extract_member(archive, ".mtx")
        payload, matrix_rows, matrix_cols, nonzeros = matrix_bitmap(source)
        split = split_by_index[index]
        output_path = destination / split / f"{name}.smb"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(payload)
        rows.append(
            {
                "domain": "sparse_matrix_pattern",
                "dataset": "SuiteSparse_HB_bcsstk",
                "split": split,
                "file": output_path.name,
                "source_url": (
                    "http://sparse-files.engr.tamu.edu/MM/HB/"
                    f"{name}.tar.gz"
                ),
                "source_sha256": sha256(archive_bytes),
                "prepared_sha256": sha256(payload),
                "prepared_bytes": len(payload),
                "records": 1,
                "shape": f"{matrix_rows}x{matrix_cols}",
                "nonzero_items": nonzeros,
                "license_status": "collection attribution recorded; redistribution not assumed",
            }
        )


def parse_idx_images(data: bytes) -> tuple[int, int, int, bytes]:
    if len(data) < 16:
        raise ValueError("truncated IDX image file")
    magic, count, rows, cols = struct.unpack(">IIII", data[:16])
    if magic != 2051 or len(data) != 16 + count * rows * cols:
        raise ValueError("invalid IDX image file")
    return count, rows, cols, data[16:]


def prepare_image_archive(
    dataset: str,
    source_name: str,
    source_url: str,
    split: str,
    rows: list[dict[str, object]],
) -> None:
    source_path = DOWNLOADS / "mnist" / source_name
    compressed = source_path.read_bytes()
    raw = gzip.decompress(compressed)
    count, image_rows, image_cols, pixels = parse_idx_images(raw)
    images_per_file = 1000
    destination = OUTPUT / "image_tensors" / dataset / split
    destination.mkdir(parents=True, exist_ok=True)
    image_bytes = image_rows * image_cols
    for shard_start in range(0, count, images_per_file):
        shard_count = min(images_per_file, count - shard_start)
        start = shard_start * image_bytes
        end = start + shard_count * image_bytes
        payload = (
            b"IMG1"
            + struct.pack(">III", shard_count, image_rows, image_cols)
            + pixels[start:end]
        )
        shard_index = shard_start // images_per_file
        output_path = destination / f"{dataset}_{split}_{shard_index:03d}.img"
        output_path.write_bytes(payload)
        rows.append(
            {
                "domain": "grayscale_image_tensor",
                "dataset": dataset,
                "split": split,
                "file": output_path.name,
                "source_url": source_url,
                "source_sha256": sha256(compressed),
                "prepared_sha256": sha256(payload),
                "prepared_bytes": len(payload),
                "records": shard_count,
                "shape": f"{image_rows}x{image_cols}",
                "nonzero_items": sum(value != 0 for value in payload[16:]),
                "license_status": (
                    "MIT repository license" if dataset == "fashion_mnist"
                    else "research benchmark; redistribution not assumed"
                ),
            }
        )


def prepare_images(rows: list[dict[str, object]]) -> None:
    sources = [
        (
            "mnist",
            "mnist-train-images.gz",
            "https://ossci-datasets.s3.amazonaws.com/mnist/train-images-idx3-ubyte.gz",
            "train",
        ),
        (
            "mnist",
            "mnist-test-images.gz",
            "https://ossci-datasets.s3.amazonaws.com/mnist/t10k-images-idx3-ubyte.gz",
            "test",
        ),
        (
            "fashion_mnist",
            "fashion-train-images.gz",
            "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/"
            "train-images-idx3-ubyte.gz",
            "train",
        ),
        (
            "fashion_mnist",
            "fashion-test-images.gz",
            "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/"
            "t10k-images-idx3-ubyte.gz",
            "test",
        ),
    ]
    for source in sources:
        prepare_image_archive(*source, rows)


def main() -> None:
    rows: list[dict[str, object]] = []
    prepare_matrices(rows)
    prepare_images(rows)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Prepared {len(rows)} real sparse-domain files")


if __name__ == "__main__":
    main()

