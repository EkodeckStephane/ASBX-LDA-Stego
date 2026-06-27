from __future__ import annotations

import csv
import hashlib
import sys
import tarfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_real_sparse_domains import matrix_bitmap  # noqa: E402

DOWNLOADS = ROOT / "data" / "downloads" / "confirmation"
OUTPUT = ROOT / "data" / "external" / "confirmation"
MANIFEST = ROOT / "manifests" / "confirmation_domains.csv"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare_matrices(rows: list[dict[str, object]]) -> None:
    destination = OUTPUT / "sparse_matrices"
    destination.mkdir(parents=True, exist_ok=True)
    for index in range(10, 13):
        name = f"bcsstk{index:02d}"
        archive_path = DOWNLOADS / f"{name}.tar.gz"
        archive_bytes = archive_path.read_bytes()
        with tarfile.open(archive_path, "r:gz") as archive:
            members = [
                member
                for member in archive.getmembers()
                if member.isfile() and member.name.lower().endswith(".mtx")
            ]
            if len(members) != 1:
                raise ValueError(f"unexpected archive layout for {name}")
            handle = archive.extractfile(members[0])
            if handle is None:
                raise ValueError(f"unable to extract {name}")
            matrix_source = handle.read()
        payload, matrix_rows, matrix_cols, nonzeros = matrix_bitmap(matrix_source)
        path = destination / f"{name}.smb"
        path.write_bytes(payload)
        rows.append(
            {
                "domain": "sparse_matrix_pattern",
                "dataset": "SuiteSparse_HB_bcsstk_confirmation",
                "file": path.name,
                "source_url": (
                    "http://sparse-files.engr.tamu.edu/MM/HB/"
                    f"{name}.tar.gz"
                ),
                "source_sha256": digest(archive_bytes),
                "prepared_sha256": digest(payload),
                "prepared_bytes": len(payload),
                "records": 1,
                "shape": f"{matrix_rows}x{matrix_cols}",
                "nonzero_items": nonzeros,
            }
        )


def prepare_kmnist(rows: list[dict[str, object]]) -> None:
    source_path = DOWNLOADS / "kmnist-test-imgs.npz"
    source_bytes = source_path.read_bytes()
    with np.load(source_path) as archive:
        images = archive["arr_0"]
    if images.ndim != 3 or images.dtype != np.uint8:
        raise ValueError("unexpected KMNIST image tensor")
    destination = OUTPUT / "kmnist"
    destination.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(images), 1000):
        shard = images[start : start + 1000]
        count, image_rows, image_cols = shard.shape
        payload = (
            b"IMG1"
            + int(count).to_bytes(4, "big")
            + int(image_rows).to_bytes(4, "big")
            + int(image_cols).to_bytes(4, "big")
            + shard.tobytes()
        )
        path = destination / f"kmnist_test_{start // 1000:03d}.img"
        path.write_bytes(payload)
        rows.append(
            {
                "domain": "grayscale_image_tensor",
                "dataset": "kmnist_confirmation",
                "file": path.name,
                "source_url": (
                    "https://codh.rois.ac.jp/kmnist/dataset/kmnist/"
                    "kmnist-test-imgs.npz"
                ),
                "source_sha256": digest(source_bytes),
                "prepared_sha256": digest(payload),
                "prepared_bytes": len(payload),
                "records": count,
                "shape": f"{image_rows}x{image_cols}",
                "nonzero_items": int(np.count_nonzero(shard)),
            }
        )


def main() -> None:
    rows: list[dict[str, object]] = []
    prepare_matrices(rows)
    prepare_kmnist(rows)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Prepared {len(rows)} untouched confirmation files")


if __name__ == "__main__":
    main()

