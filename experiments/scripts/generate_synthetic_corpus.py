from __future__ import annotations

import json
import random
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "reference.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "data" / "synthetic"


def boundary_zero_blocks(size: int, block_size: int, rng: random.Random) -> bytes:
    output = bytearray()
    while len(output) < size:
        left = rng.randrange(0, block_size // 2 + 1)
        right = rng.randrange(0, block_size // 2 + 1)
        middle_length = max(0, block_size - left - right)
        middle = bytes(rng.randrange(1, 256) for _ in range(middle_length))
        output += bytes(left) + middle + bytes(right)
    return bytes(output[:size])


def sparse_bits(size: int, probability: float, rng: random.Random) -> bytes:
    output = bytearray(size)
    for bit_position in range(size * 8):
        if rng.random() < probability:
            byte_index, bit_index = divmod(bit_position, 8)
            output[byte_index] |= 1 << (7 - bit_index)
    return bytes(output)


def clustered_bits(size: int, rng: random.Random) -> bytes:
    output = bytearray(size)
    for _ in range(max(1, size // 256)):
        start = rng.randrange(0, size * 8)
        run = rng.randrange(8, 129)
        for position in range(start, min(size * 8, start + run)):
            byte_index, bit_index = divmod(position, 8)
            output[byte_index] |= 1 << (7 - bit_index)
    return bytes(output)


def generate_suite(size: int, seed: int) -> dict[str, bytes]:
    rng = random.Random(seed)
    zero_block_stream = bytearray()
    block_size = 256
    while len(zero_block_stream) < size:
        if rng.random() < 0.75:
            zero_block_stream += bytes(block_size)
        else:
            zero_block_stream += rng.randbytes(block_size)

    return {
        "all_zero.bin": bytes(size),
        "all_one.bin": b"\xff" * size,
        "random.bin": rng.randbytes(size),
        "zero_blocks_75.bin": bytes(zero_block_stream[:size]),
        "boundary_zeros.bin": boundary_zero_blocks(size, block_size, rng),
        "sparse_bits_001.bin": sparse_bits(size, 0.001, rng),
        "sparse_bits_01.bin": sparse_bits(size, 0.01, rng),
        "dense_bits_99.bin": sparse_bits(size, 0.99, rng),
        "clustered_bits.bin": clustered_bits(size, rng),
    }


def main() -> None:
    size = int(CONFIG["synthetic_bytes_per_file"])
    base_seed = int(CONFIG["seed"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    total = 0
    for split, offset in CONFIG["synthetic_splits"].items():
        seed = base_seed + int(offset)
        split_output = OUTPUT / split
        split_output.mkdir(parents=True, exist_ok=True)
        files = generate_suite(size, seed)
        for name, payload in files.items():
            path = split_output / name
            path.write_bytes(payload)
            manifest_rows.append(
                {
                    "split": split,
                    "file": name,
                    "seed": seed,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            total += 1

    manifest = ROOT / "manifests" / "synthetic.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Generated {total} deterministic files of {size} bytes in {OUTPUT}")


if __name__ == "__main__":
    main()
