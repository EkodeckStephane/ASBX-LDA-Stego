from __future__ import annotations

import csv
import hashlib
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "generated_large"
MANIFEST = ROOT / "manifests" / "generated_large.csv"


def sparse_bits(size: int, probability: float, rng: random.Random) -> bytes:
    data = bytearray(size)
    for bit_position in range(size * 8):
        if rng.random() < probability:
            byte_index, bit_index = divmod(bit_position, 8)
            data[byte_index] |= 1 << (7 - bit_index)
    return bytes(data)


def zero_bursts(size: int, block_size: int, rng: random.Random) -> bytes:
    data = bytearray()
    while len(data) < size:
        if rng.random() < 0.82:
            data += bytes(block_size)
        else:
            data += rng.randbytes(block_size)
    return bytes(data[:size])


def sparse_records(size: int, rng: random.Random) -> bytes:
    data = bytearray(size)
    cursor = 0
    while cursor < size:
        record_length = rng.randrange(24, 96)
        if rng.random() < 0.18:
            token = f"id={cursor:08x};value={rng.randrange(1, 1_000_000)}\n".encode("ascii")
            data[cursor : min(size, cursor + len(token))] = token[: max(0, size - cursor)]
        cursor += record_length
    return bytes(data)


def make_payloads(seed: int) -> dict[str, bytes]:
    rng = random.Random(seed)
    return {
        "large_sparse_bits_0005.bin": sparse_bits(1 * 1024 * 1024, 0.0005, rng),
        "large_sparse_bits_005.bin": sparse_bits(1 * 1024 * 1024, 0.005, rng),
        "large_zero_bursts.bin": zero_bursts(2 * 1024 * 1024, 256, rng),
        "large_sparse_records.bin": sparse_records(2 * 1024 * 1024, rng),
        "large_random_control.bin": rng.randbytes(1 * 1024 * 1024),
    }


def main() -> None:
    seed = 20260627
    OUTPUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, payload in make_payloads(seed).items():
        path = OUTPUT / name
        path.write_bytes(payload)
        rows.append(
            {
                "file": name,
                "seed": seed,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "generator": Path(__file__).name,
            }
        )

    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} large deterministic payloads in {OUTPUT}")


if __name__ == "__main__":
    main()
