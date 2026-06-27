from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import (  # noqa: E402
    MAGIC,
    STREAM_BLOCKS,
    STREAM_RAW,
    VERSION,
    decode,
    encode,
)
from asbc.modes import Mode  # noqa: E402
from asbc.varint import decode_uvarint  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "reference.json").read_text(encoding="utf-8"))
DATA = ROOT / "data" / "synthetic"
RESULTS = ROOT / "results"


def mode_counts(container: bytes) -> tuple[str, Counter[str]]:
    if not container.startswith(MAGIC + bytes([VERSION])):
        raise ValueError("unexpected campaign format")
    offset = len(MAGIC) + 1
    stream_mode = container[offset]
    _, offset = decode_uvarint(container, offset + 1)
    if stream_mode == STREAM_RAW:
        return "raw", Counter()
    if stream_mode != STREAM_BLOCKS:
        raise ValueError("unexpected campaign stream mode")
    _, offset = decode_uvarint(container, offset)
    block_count, offset = decode_uvarint(container, offset)
    counts: Counter[str] = Counter()
    for _ in range(block_count):
        mode = Mode(container[offset])
        _, offset = decode_uvarint(container, offset + 1)
        payload_length, offset = decode_uvarint(container, offset)
        offset += payload_length
        counts[mode.name.lower()] += 1
    if offset != len(container):
        raise ValueError("campaign parser found trailing bytes")
    return "adaptive", counts


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(DATA.glob("train/*.bin")):
        source = path.read_bytes()
        for block_size in CONFIG["block_sizes"]:
            started = time.perf_counter()
            container = encode(source, int(block_size))
            encode_seconds = time.perf_counter() - started
            started = time.perf_counter()
            restored = decode(container)
            decode_seconds = time.perf_counter() - started
            if restored != source:
                raise RuntimeError(f"round-trip mismatch for {path.name}")
            stream_mode, counts = mode_counts(container)
            rows.append(
                {
                    "file": path.name,
                    "split": path.parent.name,
                    "block_size": block_size,
                    "original_bytes": len(source),
                    "encoded_bytes": len(container),
                    "ratio": len(container) / len(source) if source else 0.0,
                    "encode_seconds": encode_seconds,
                    "decode_seconds": decode_seconds,
                    "stream_mode": stream_mode,
                    **{
                        f"blocks_{mode.name.lower()}": counts[mode.name.lower()]
                        for mode in Mode
                    },
                }
            )

    output = RESULTS / "reference_campaign.csv"
    fieldnames = list(rows[0]) if rows else []
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} verified measurements to {output}")


if __name__ == "__main__":
    main()
