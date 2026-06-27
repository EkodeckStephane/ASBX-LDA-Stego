"""Practical ASBX benchmark for the SPE manuscript.

The capacity benchmark answers a steganographic question.  This script answers
the software-engineering question expected by Software: Practice and
Experience: how the reference implementation behaves under different block
sizes, and how its practical costs compare with standard library compressors.

Outputs
-------
  SPE/results/practical_benchmark.csv
  SPE/results/practical_benchmark_summary.csv
  SPE/LDA_Stego_ASBX/tables/tab_practical_benchmark.tex
"""

from __future__ import annotations

import bz2
import csv
import lzma
import statistics
import sys
import time
import tracemalloc
import zlib
from collections import defaultdict
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_FISA_ROOT = _REPO_ROOT.parent / "Fibonacci_Inspired_Entropy_Reduction"
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))

from asbc import decode as asbx_decode  # noqa: E402
from asbc import encode_deterministic as asbx_encode  # noqa: E402

_RESULTS_DIR = _HERE.parent / "results"
_TABLES_DIR = _HERE.parent / "LDA_Stego_ASBX" / "tables"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_TABLES_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_LIMITS = {
    "sparse_matrix": 2,
    "image_tensor": 2,
    "canterbury_text": 2,
    "silesia_mixed": 2,
    "synthetic": 3,
}
ASBX_BLOCK_SIZES = [64, 256, 1024]
MAX_PAYLOAD_BYTES = 8192


def _read_existing(paths: list[Path], domain: str, limit: int) -> Iterator[tuple[str, str, bytes]]:
    yielded = 0
    for path in paths:
        if yielded >= limit:
            break
        if not path.exists():
            continue
        data = path.read_bytes()
        data = data[:MAX_PAYLOAD_BYTES]
        yielded += 1
        yield domain, path.name, data


def _synthetic_payloads() -> Iterator[tuple[str, str, bytes]]:
    rng = np.random.default_rng(2026)
    size = MAX_PAYLOAD_BYTES
    for rho in [0.01, 0.05, 0.50]:
        bits = (rng.random(size * 8) < rho).astype(np.uint8)
        data = bytearray(size)
        for i in range(size):
            value = 0
            for j in range(8):
                value |= int(bits[i * 8 + j]) << (7 - j)
            data[i] = value
        yield "synthetic", f"rho_{rho:.2f}", bytes(data)
    yield "synthetic", "all_zero", b"\x00" * size


def payloads() -> Iterator[tuple[str, str, bytes]]:
    exp = _REPO_ROOT / "experiments"
    fisa_exp = _FISA_ROOT / "experiments"

    yield from _read_existing(
        [
            exp / "data" / "external" / "confirmation" / "sparse_matrices" / f"{name}.smb"
            for name in ["bcsstk10", "bcsstk11", "bcsstk12"]
        ],
        "sparse_matrix",
        SAMPLE_LIMITS["sparse_matrix"],
    )

    yield from _read_existing(
        [
            exp / "data" / "external" / "confirmation" / "kmnist" / f"kmnist_test_{i:03d}.img"
            for i in range(10)
        ],
        "image_tensor",
        SAMPLE_LIMITS["image_tensor"],
    )

    yield from _read_existing(
        [
            fisa_exp / "data" / "canterbury" / name
            for name in ["alice29.txt", "asyoulik.txt", "cp.html", "fields.c"]
        ],
        "canterbury_text",
        SAMPLE_LIMITS["canterbury_text"],
    )

    yield from _read_existing(
        [
            fisa_exp / "data" / "silesia" / name
            for name in ["dickens", "mozilla", "mr", "nci"]
        ],
        "silesia_mixed",
        SAMPLE_LIMITS["silesia_mixed"],
    )

    yield from _synthetic_payloads()


def _measure(
    encode: Callable[[bytes], bytes],
    decode: Callable[[bytes], bytes],
    data: bytes,
) -> tuple[bytes, float, float, int, bool]:
    tracemalloc.start()
    start = time.perf_counter()
    encoded = encode(data)
    encode_ms = (time.perf_counter() - start) * 1000.0
    _, peak_encode = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    start = time.perf_counter()
    recovered = decode(encoded)
    decode_ms = (time.perf_counter() - start) * 1000.0
    _, peak_decode = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return encoded, encode_ms, decode_ms, max(peak_encode, peak_decode), recovered == data


def run() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    compressors: list[tuple[str, str, Callable[[bytes], bytes], Callable[[bytes], bytes]]] = []

    for block_size in ASBX_BLOCK_SIZES:
        compressors.append(
            (
                "asbx",
                str(block_size),
                lambda data, b=block_size: asbx_encode(data, block_size=b),
                asbx_decode,
            )
        )

    compressors.extend(
        [
            ("zlib", "default", zlib.compress, zlib.decompress),
            ("bz2", "default", bz2.compress, bz2.decompress),
            ("lzma", "preset6", lzma.compress, lzma.decompress),
        ]
    )

    loaded = list(payloads())
    print(f"Loaded {len(loaded)} payloads for practical benchmarking.")

    for domain, name, data in loaded:
        for method, setting, enc, dec in compressors:
            encoded, enc_ms, dec_ms, peak_bytes, ok = _measure(enc, dec, data)
            row = {
                "domain": domain,
                "payload": name,
                "method": method,
                "setting": setting,
                "input_bytes": len(data),
                "encoded_bytes": len(encoded),
                "ratio": round(len(encoded) / len(data), 6),
                "encode_ms": round(enc_ms, 3),
                "decode_ms": round(dec_ms, 3),
                "peak_kib": round(peak_bytes / 1024.0, 1),
                "round_trip_ok": ok,
            }
            rows.append(row)
            print(
                f"{domain:16s} {name:18s} {method:5s} {setting:7s} "
                f"R={row['ratio']:.4f} enc={row['encode_ms']:.1f}ms ok={ok}"
            )

    return rows


def write_csv(rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError("no benchmark rows produced")
    with (_RESULTS_DIR / "practical_benchmark.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarise(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["domain"]), str(row["method"]), str(row["setting"]))].append(row)

    summary: list[dict[str, object]] = []
    for (domain, method, setting), items in sorted(groups.items()):
        summary.append(
            {
                "domain": domain,
                "method": method,
                "setting": setting,
                "n": len(items),
                "median_ratio": round(statistics.median(float(x["ratio"]) for x in items), 6),
                "median_encode_ms": round(statistics.median(float(x["encode_ms"]) for x in items), 3),
                "median_decode_ms": round(statistics.median(float(x["decode_ms"]) for x in items), 3),
                "median_peak_kib": round(statistics.median(float(x["peak_kib"]) for x in items), 1),
                "all_round_trips_ok": all(bool(x["round_trip_ok"]) for x in items),
            }
        )

    with (_RESULTS_DIR / "practical_benchmark_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    return summary


def write_latex_table(summary: list[dict[str, object]]) -> None:
    selected = [
        row
        for row in summary
        if (row["method"] == "asbx" and row["setting"] in {"64", "256", "1024"})
        or (row["method"] in {"zlib", "bz2", "lzma"} and row["setting"] in {"default", "preset6"})
    ]
    domains = ["sparse_matrix", "image_tensor", "canterbury_text", "silesia_mixed", "synthetic"]
    method_order = {
        ("asbx", "64"): 0,
        ("asbx", "256"): 1,
        ("asbx", "1024"): 2,
        ("zlib", "default"): 3,
        ("bz2", "default"): 4,
        ("lzma", "preset6"): 5,
    }
    selected.sort(key=lambda r: (domains.index(str(r["domain"])), method_order[(str(r["method"]), str(r["setting"]))]))

    lines = [
        "% Generated by SPE/code/practical_benchmark.py",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Practical codec behaviour on representative local payloads. "
        "Ratios and costs are medians over files in each domain; timings are for "
        "the single-threaded Python reference on the author workstation.}",
        "\\label{tab:practical-benchmark}",
        "\\small",
        "\\begin{tabular}{@{}llrrrrr@{}}",
        "\\toprule",
        "Domain & Method & $n$ & $R$ & Enc. ms & Dec. ms & Peak KiB \\\\",
        "\\midrule",
    ]
    labels = {
        "sparse_matrix": "Sparse matrices",
        "image_tensor": "KMNIST tensors",
        "canterbury_text": "Canterbury",
        "silesia_mixed": "Silesia",
        "synthetic": "Synthetic",
    }
    for row in selected:
        method = str(row["method"]).upper()
        if row["method"] == "asbx":
            method = f"ASBX-{row['setting']}"
        lines.append(
            f"{labels[str(row['domain'])]} & {method} & {row['n']} & "
            f"{float(row['median_ratio']):.3f} & "
            f"{float(row['median_encode_ms']):.1f} & "
            f"{float(row['median_decode_ms']):.1f} & "
            f"{float(row['median_peak_kib']):.0f} \\\\"
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )
    (_TABLES_DIR / "tab_practical_benchmark.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = run()
    write_csv(rows)
    summary = summarise(rows)
    write_latex_table(summary)
    if not all(bool(row["round_trip_ok"]) for row in rows):
        raise SystemExit("at least one round-trip failed")
    print("Practical benchmark complete.")


if __name__ == "__main__":
    main()
