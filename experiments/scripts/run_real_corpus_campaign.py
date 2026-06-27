from __future__ import annotations

import bz2
import csv
import hashlib
import json
import lzma
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import decode, encode, encode_fixed, encode_with_selector  # noqa: E402
from asbc.modes import Mode  # noqa: E402
from asbc.selector import deterministic_candidate  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "reference.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
MANIFESTS = ROOT / "manifests"
REFERENCE_DATA = Path(
    r"C:\Users\User\Documents\results\Fibonacci_Inspired_Entropy_Reduction"
    r"\experiments\data"
)


def measured(method, source: bytes) -> tuple[bytes, float]:
    started = time.perf_counter()
    result = method(source)
    return result, time.perf_counter() - started


def main() -> None:
    block_size = int(CONFIG["selector_block_size"])
    datasets = {
        "canterbury": REFERENCE_DATA / "canterbury",
        "silesia_sample": REFERENCE_DATA / "silesia_sample",
    }
    asbx_methods = {
        "asbx_oracle": lambda data: encode(data, block_size),
        "asbx_deterministic": lambda data: encode_with_selector(
            data, block_size, deterministic_candidate
        ),
        **{
            f"asbx_fixed_{mode.name.lower()}": (
                lambda data, selected=mode: encode_fixed(data, selected, block_size)
            )
            for mode in Mode
        },
    }
    baseline_methods = {
        "zlib_9": lambda data: zlib.compress(data, 9),
        "bzip2_9": lambda data: bz2.compress(data, compresslevel=9),
        "lzma_9": lambda data: lzma.compress(data, preset=9),
    }

    rows = []
    manifest_rows = []
    for corpus, directory in datasets.items():
        for path in sorted(item for item in directory.iterdir() if item.is_file()):
            source = path.read_bytes()
            manifest_rows.append(
                {
                    "corpus": corpus,
                    "file": path.name,
                    "source_path": str(path),
                    "bytes": len(source),
                    "sha256": hashlib.sha256(source).hexdigest(),
                }
            )
            for method_name, method in {**asbx_methods, **baseline_methods}.items():
                payload, seconds = measured(method, source)
                if method_name.startswith("asbx_") and decode(payload) != source:
                    raise RuntimeError(
                        f"round-trip mismatch: {corpus}/{path.name}/{method_name}"
                    )
                rows.append(
                    {
                        "corpus": corpus,
                        "file": path.name,
                        "method": method_name,
                        "block_size": block_size if method_name.startswith("asbx_") else "",
                        "original_bytes": len(source),
                        "encoded_bytes": len(payload),
                        "ratio": len(payload) / len(source) if source else 0.0,
                        "encode_seconds": seconds,
                    }
                )

    RESULTS.mkdir(parents=True, exist_ok=True)
    measurements = RESULTS / "real_corpus_measurements.csv"
    with measurements.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    MANIFESTS.mkdir(parents=True, exist_ok=True)
    manifest = MANIFESTS / "real_corpora.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote {len(rows)} real-file measurements for {len(manifest_rows)} files")


if __name__ == "__main__":
    main()

