"""Embedding-capacity benchmark for ASBX-Enhanced LDA Text Steganography.

Measures, for each payload type, how ASBX pre-compression changes:
  - the number of stego words required to embed the same secret
  - the effective embedding capacity gain factor (1/ASBX_ratio)
  - the round-trip decoding correctness

Payload types tested
--------------------
  sparse_matrix   : bcsstk10-12 SMB files (ASBX ratio ~0.076)
  image_tensor    : KMNIST test shards  (ASBX ratio ~0.648)
  natural_text    : Canterbury/Silesia files (ASBX ratio ~0.887)
  synthetic_sparse: randomly generated bit vectors with density ρ ∈ {1%, 5%, 10%}
  synthetic_dense : random uniform bytes (negative control)

Output
------
  SPE/results/capacity_results.csv
  SPE/results/capacity_results.json
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Iterator

import numpy as np

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_FISA_ROOT = _REPO_ROOT.parent / "Fibonacci_Inspired_Entropy_Reduction"
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))

from asbc import encode as asbx_encode, decode as asbx_decode  # noqa: E402
from payload_encoder import encode_payload, embedding_stats  # noqa: E402
from payload_decoder import decode_payload  # noqa: E402

_RESULTS_DIR = _HERE.parent / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ASBX parameters
BLOCK_SIZE = 256
NUM_TOPICS = 64
K_BITS = int(math.log2(NUM_TOPICS))
ASBX_SELECTOR = "deterministic"

# Known ASBX ratios from the ASBX paper (complete serialised cost, oracle selector)
_KNOWN_RATIOS = {
    "bcsstk10": 0.1165,
    "bcsstk11": 0.0650,
    "bcsstk12": 0.0650,
    "kmnist_test_mean": 0.6477,
    "canterbury_mean": 0.8871,
    "silesia_mean": 0.9397,
}


# ---------------------------------------------------------------------------
# Payload generators
# ---------------------------------------------------------------------------

def _read_file_payloads(paths: list[Path], label: str) -> Iterator[tuple[str, bytes]]:
    for p in paths:
        if p.exists():
            yield f"{label}/{p.name}", p.read_bytes()
        else:
            print(f"  [SKIP] {p} not found", flush=True)


def _synthetic_payloads() -> Iterator[tuple[str, bytes]]:
    rng = np.random.default_rng(0)
    sizes = [1024, 4096, 16384]
    densities = [0.01, 0.05, 0.10, 0.50, 1.00]
    for size in sizes:
        for rho in densities:
            bits = (rng.random(size * 8) < rho).astype(np.uint8)
            # Pack into bytes
            data = bytearray(size)
            for i in range(size):
                byte_val = 0
                for j in range(8):
                    byte_val |= int(bits[i * 8 + j]) << (7 - j)
                data[i] = byte_val
            label = f"synthetic_rho{int(rho*100):03d}_size{size}"
            yield label, bytes(data)


# ---------------------------------------------------------------------------
# Benchmark core
# ---------------------------------------------------------------------------

def _benchmark_one(label: str, secret: bytes) -> dict:
    if len(secret) == 0:
        return {}

    # ASBX encode
    indices, compressed = encode_payload(secret, NUM_TOPICS, BLOCK_SIZE, selector=ASBX_SELECTOR)
    stats = embedding_stats(secret, compressed, NUM_TOPICS, num_cover_words=len(indices))

    # Verify round-trip
    recovered = decode_payload(indices, K_BITS, len(compressed))
    ok = recovered == secret

    # Baseline: no compression (raw bytes → topic indices)
    raw_indices_count = math.ceil(len(secret) * 8 / K_BITS)

    return {
        "label": label,
        "secret_bytes": len(secret),
        "compressed_bytes": len(compressed),
        "asbx_ratio": round(stats["asbx_ratio"], 6),
        "k_bits_per_word": K_BITS,
        "asbx_selector": ASBX_SELECTOR,
        "words_with_asbx": len(indices),
        "words_without_asbx": raw_indices_count,
        "capacity_gain_factor": round(stats["capacity_gain_factor"], 4),
        "round_trip_ok": ok,
    }


# ---------------------------------------------------------------------------
# File corpus paths
# ---------------------------------------------------------------------------

def _corpus_paths() -> dict[str, list[Path]]:
    exp = _REPO_ROOT / "experiments"
    fisa_exp = _FISA_ROOT / "experiments"
    return {
        "sparse_matrix": [
            exp / "data" / "external" / "confirmation" / "sparse_matrices" / f"{name}.smb"
            for name in ["bcsstk10", "bcsstk11", "bcsstk12"]
        ],
        "image_tensor": [
            exp / "data" / "external" / "confirmation" / "kmnist" / f"kmnist_test_{i:03d}.img"
            for i in range(10)
        ],
        "canterbury": [
            fisa_exp / "data" / "canterbury" / name
            for name in [
                "alice29.txt", "asyoulik.txt", "cp.html", "fields.c",
                "grammar.lsp", "kennedy.xls", "lcet10.txt",
                "plrabn12.txt", "ptt5", "sum", "xargs.1",
            ]
        ],
        "silesia": [
            fisa_exp / "data" / "silesia" / name
            for name in ["dickens", "mozilla", "mr", "nci", "ooffice",
                         "osdb", "reymont", "samba", "sao", "webster",
                         "x-ray", "xml"]
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmark() -> list[dict]:
    rows: list[dict] = []
    paths = _corpus_paths()

    for corpus_label, file_list in paths.items():
        print(f"\n--- {corpus_label} ---")
        for name, data in _read_file_payloads(file_list, corpus_label):
            # Use first 65536 bytes for Silesia (matches ASBX paper protocol)
            payload = data[:65536] if corpus_label in ("silesia", "canterbury") else data
            row = _benchmark_one(name, payload)
            if row:
                rows.append(row)
                gain = row["capacity_gain_factor"]
                print(f"  {name:45s}  ratio={row['asbx_ratio']:.4f}  gain=×{gain:.2f}  rt={row['round_trip_ok']}")

    print("\n--- synthetic ---")
    for name, payload in _synthetic_payloads():
        row = _benchmark_one(name, payload)
        if row:
            rows.append(row)
            gain = row["capacity_gain_factor"]
            print(f"  {name:45s}  ratio={row['asbx_ratio']:.4f}  gain=×{gain:.2f}  rt={row['round_trip_ok']}")

    return rows


def save_results(rows: list[dict]) -> None:
    if not rows:
        print("No results to save.")
        return

    csv_path = _RESULTS_DIR / "capacity_results.csv"
    json_path = _RESULTS_DIR / "capacity_results.json"

    fieldnames = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    print(f"\nResults -> {csv_path}")
    print(f"Results -> {json_path}")

    # Summary statistics by corpus type
    print("\n=== Summary ===")
    from collections import defaultdict
    by_corpus: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        corpus = row["label"].split("/")[0]
        by_corpus[corpus].append(row["capacity_gain_factor"])

    for corpus, gains in sorted(by_corpus.items()):
        print(f"  {corpus:20s}  mean gain ×{sum(gains)/len(gains):.2f}  "
              f"  min ×{min(gains):.2f}  max ×{max(gains):.2f}  n={len(gains)}")


if __name__ == "__main__":
    print("ASBX-Enhanced LDA Steganography — Capacity Benchmark")
    print(f"  T={NUM_TOPICS} topics, k={K_BITS} bits/word, block_size={BLOCK_SIZE}")
    rows = run_benchmark()
    save_results(rows)

    all_ok = all(r.get("round_trip_ok", False) for r in rows)
    print(f"\nAll round-trips OK: {all_ok}")
    if not all_ok:
        failed = [r["label"] for r in rows if not r.get("round_trip_ok", False)]
        print(f"FAILED: {failed}")
        sys.exit(1)
