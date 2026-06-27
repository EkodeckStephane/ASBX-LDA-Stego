"""Broad software benchmark for ASBX as a journal artefact.

This script complements the short memory benchmark.  It evaluates ASBX as a
codec implementation across a wider local corpus, compares the deterministic
selector against the exact oracle, sweeps block size, and reports standard
library compressor baselines.  Inputs are capped to keep the script suitable
for routine reproducibility on a laptop.

Outputs
-------
  SPE/results/software_benchmark.csv
  SPE/results/software_benchmark_summary.csv
  SPE/LDA_Stego_ASBX/tables/tab_selector_regret.tex
  SPE/LDA_Stego_ASBX/tables/tab_software_benchmark.tex
"""

from __future__ import annotations

import bz2
import csv
import lzma
import statistics
import sys
import time
import zlib
from collections import defaultdict
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

try:
    import brotli
except ImportError:  # pragma: no cover - optional baseline
    brotli = None

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover - optional baseline
    zstd = None

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_FISA_ROOT = _REPO_ROOT.parent / "Fibonacci_Inspired_Entropy_Reduction"
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))

from asbc import decode, encode, encode_deterministic  # noqa: E402

_RESULTS_DIR = _HERE.parent / "results"
_TABLES_DIR = _HERE.parent / "LDA_Stego_ASBX" / "tables"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_TABLES_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 16384
ASBX_BLOCK_SIZES = [64, 256, 1024]


def _take(path: Path, domain: str, name: str | None = None) -> tuple[str, str, bytes] | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()[:MAX_BYTES]
    if not data:
        return None
    return domain, name or path.name, data


def _existing(paths: list[Path], domain: str, limit: int) -> Iterator[tuple[str, str, bytes]]:
    count = 0
    for path in paths:
        item = _take(path, domain)
        if item is None:
            continue
        yield item
        count += 1
        if count >= limit:
            break


def _synthetic() -> Iterator[tuple[str, str, bytes]]:
    rng = np.random.default_rng(20260627)
    size = MAX_BYTES
    for rho in [0.001, 0.01, 0.05, 0.10, 0.50, 0.99, 1.0]:
        bits = (rng.random(size * 8) < rho).astype(np.uint8)
        data = bytearray(size)
        for i in range(size):
            value = 0
            for j in range(8):
                value |= int(bits[i * 8 + j]) << (7 - j)
            data[i] = value
        yield "synthetic", f"rho_{rho:g}", bytes(data)
    yield "synthetic", "zero_blocks_75", (bytes(512) + bytes(range(256)) * 2) * 8
    yield "synthetic", "boundary_zeros", bytes(4096) + b"payload" * 256 + bytes(4096)


def payloads() -> list[tuple[str, str, bytes]]:
    exp = _REPO_ROOT / "experiments"
    fisa = _FISA_ROOT / "experiments"
    items: list[tuple[str, str, bytes]] = []

    sparse_paths = sorted((exp / "data" / "external" / "sparse_matrices").glob("*/*.smb"))
    sparse_paths += sorted((exp / "data" / "external" / "confirmation" / "sparse_matrices").glob("*.smb"))
    items.extend(_existing(sparse_paths, "sparse_matrix", limit=15))

    image_roots = [
        exp / "data" / "external" / "confirmation" / "kmnist",
        exp / "data" / "external" / "image_tensors" / "mnist" / "test",
        exp / "data" / "external" / "image_tensors" / "mnist" / "train",
        exp / "data" / "external" / "image_tensors" / "fashion_mnist" / "test",
        exp / "data" / "external" / "image_tensors" / "fashion_mnist" / "train",
    ]
    for root in image_roots:
        items.extend(_existing(sorted(root.glob("*.img")), "image_tensor", limit=4))

    items.extend(
        _existing(
            [
                fisa / "data" / "canterbury" / name
                for name in [
                    "alice29.txt",
                    "asyoulik.txt",
                    "cp.html",
                    "fields.c",
                    "grammar.lsp",
                    "lcet10.txt",
                    "plrabn12.txt",
                    "xargs.1",
                ]
            ],
            "text_control",
            limit=8,
        )
    )
    items.extend(
        _existing(
            [
                fisa / "data" / "silesia" / name
                for name in [
                    "dickens",
                    "mozilla",
                    "mr",
                    "nci",
                    "ooffice",
                    "samba",
                    "webster",
                    "xml",
                ]
            ],
            "mixed_control",
            limit=8,
        )
    )
    items.extend(_synthetic())

    seen: set[tuple[str, str]] = set()
    unique = []
    for domain, name, data in items:
        key = (domain, name)
        if key not in seen:
            unique.append((domain, name, data))
            seen.add(key)
    return unique


def _measure(encode_fn: Callable[[bytes], bytes], decode_fn: Callable[[bytes], bytes], data: bytes) -> tuple[int, float, float, bool]:
    start = time.perf_counter()
    encoded = encode_fn(data)
    encode_ms = (time.perf_counter() - start) * 1000.0
    start = time.perf_counter()
    recovered = decode_fn(encoded)
    decode_ms = (time.perf_counter() - start) * 1000.0
    return len(encoded), encode_ms, decode_ms, recovered == data


def _zstd_compress(data: bytes) -> bytes:
    compressor = zstd.ZstdCompressor(level=3)
    return compressor.compress(data)


def _zstd_decompress(data: bytes) -> bytes:
    decompressor = zstd.ZstdDecompressor()
    return decompressor.decompress(data)


def run() -> list[dict[str, object]]:
    corpus = payloads()
    print(f"Loaded {len(corpus)} benchmark payloads, capped at {MAX_BYTES} bytes each.")
    rows: list[dict[str, object]] = []

    methods: list[tuple[str, str, Callable[[bytes], bytes], Callable[[bytes], bytes]]] = []
    for block_size in ASBX_BLOCK_SIZES:
        methods.append(
            (
                "asbx-deterministic",
                str(block_size),
                lambda data, b=block_size: encode_deterministic(data, block_size=b),
                decode,
            )
        )
    methods.append(("asbx-oracle", "256", lambda data: encode(data, block_size=256), decode))
    methods.extend(
        [
            ("zlib", "default", zlib.compress, zlib.decompress),
            ("bz2", "default", bz2.compress, bz2.decompress),
            ("lzma", "preset6", lzma.compress, lzma.decompress),
        ]
    )
    if brotli is not None:
        methods.append(("brotli", "quality5", lambda data: brotli.compress(data, quality=5), brotli.decompress))
    if zstd is not None:
        methods.append(("zstd", "level3", _zstd_compress, _zstd_decompress))

    for domain, payload_name, data in corpus:
        for method, setting, enc, dec in methods:
            encoded_bytes, encode_ms, decode_ms, ok = _measure(enc, dec, data)
            row = {
                "domain": domain,
                "payload": payload_name,
                "input_bytes": len(data),
                "method": method,
                "setting": setting,
                "encoded_bytes": encoded_bytes,
                "ratio": round(encoded_bytes / len(data), 6),
                "encode_ms": round(encode_ms, 3),
                "decode_ms": round(decode_ms, 3),
                "encode_mib_s": round((len(data) / (1024 * 1024)) / max(encode_ms / 1000.0, 1e-12), 3),
                "decode_mib_s": round((len(data) / (1024 * 1024)) / max(decode_ms / 1000.0, 1e-12), 3),
                "round_trip_ok": ok,
            }
            rows.append(row)
        print(f"  {domain:14s} {payload_name:28s} done")
    return rows


def write_csv(rows: list[dict[str, object]]) -> None:
    with (_RESULTS_DIR / "software_benchmark.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["domain"]), str(row["method"]), str(row["setting"]))].append(row)

    summary = []
    for (domain, method, setting), items in sorted(groups.items()):
        summary.append(
            {
                "domain": domain,
                "method": method,
                "setting": setting,
                "n": len(items),
                "median_ratio": round(statistics.median(float(x["ratio"]) for x in items), 6),
                "mean_ratio": round(statistics.fmean(float(x["ratio"]) for x in items), 6),
                "median_encode_mib_s": round(statistics.median(float(x["encode_mib_s"]) for x in items), 3),
                "median_decode_mib_s": round(statistics.median(float(x["decode_mib_s"]) for x in items), 3),
                "all_round_trips_ok": all(bool(x["round_trip_ok"]) for x in items),
            }
        )

    with (_RESULTS_DIR / "software_benchmark_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    return summary


def selector_regret(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_file: dict[tuple[str, str], dict[tuple[str, str], dict[str, object]]] = defaultdict(dict)
    for row in rows:
        by_file[(str(row["domain"]), str(row["payload"]))][(str(row["method"]), str(row["setting"]))] = row

    regrets: list[dict[str, object]] = []
    for (domain, payload_name), methods in by_file.items():
        det = methods.get(("asbx-deterministic", "256"))
        oracle = methods.get(("asbx-oracle", "256"))
        if det is None or oracle is None:
            continue
        oracle_bytes = int(oracle["encoded_bytes"])
        det_bytes = int(det["encoded_bytes"])
        regrets.append(
            {
                "domain": domain,
                "payload": payload_name,
                "deterministic_ratio": float(det["ratio"]),
                "oracle_ratio": float(oracle["ratio"]),
                "regret_pct": round(100.0 * (det_bytes - oracle_bytes) / max(oracle_bytes, 1), 3),
            }
        )
    return regrets


def write_tables(summary: list[dict[str, object]], regrets: list[dict[str, object]]) -> None:
    domain_labels = {
        "sparse_matrix": "Sparse matrices",
        "image_tensor": "Image tensors",
        "text_control": "Text controls",
        "mixed_control": "Mixed controls",
        "synthetic": "Synthetic",
    }
    selected_methods = {
        ("asbx-deterministic", "256"): "ASBX-det",
        ("asbx-oracle", "256"): "ASBX-oracle",
        ("zlib", "default"): "zlib",
        ("zstd", "level3"): "zstd",
        ("brotli", "quality5"): "Brotli",
        ("bz2", "default"): "bz2",
        ("lzma", "preset6"): "lzma",
    }
    ordered_domains = ["sparse_matrix", "image_tensor", "text_control", "mixed_control", "synthetic"]

    lines = [
        "% Generated by SPE/code/software_benchmark.py",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Broad software benchmark on local 16 KiB payload prefixes. "
        "Ratios and throughputs are domain medians.}",
        "\\label{tab:software-benchmark}",
        "\\small",
        "\\begin{tabular}{@{}llrrrr@{}}",
        "\\toprule",
        "Domain & Method & $n$ & $R$ & Enc. MiB/s & Dec. MiB/s \\\\",
        "\\midrule",
    ]
    lookup = {(row["domain"], row["method"], row["setting"]): row for row in summary}
    for domain in ordered_domains:
        for key, label in selected_methods.items():
            row = lookup.get((domain, key[0], key[1]))
            if row is None:
                continue
            lines.append(
                f"{domain_labels[domain]} & {label} & {row['n']} & "
                f"{float(row['median_ratio']):.3f} & "
                f"{float(row['median_encode_mib_s']):.2f} & "
                f"{float(row['median_decode_mib_s']):.2f} \\\\"
            )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    (_TABLES_DIR / "tab_software_benchmark.tex").write_text("\n".join(lines), encoding="utf-8")

    regret_groups: dict[str, list[float]] = defaultdict(list)
    for row in regrets:
        regret_groups[str(row["domain"])].append(float(row["regret_pct"]))
    lines = [
        "% Generated by SPE/code/software_benchmark.py",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Deterministic selector regret relative to the exact ASBX oracle at block size 256.}",
        "\\label{tab:selector-regret}",
        "\\small",
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\toprule",
        "Domain & $n$ & Median regret & Mean regret & Max regret \\\\",
        "\\midrule",
    ]
    for domain in ordered_domains:
        values = regret_groups.get(domain, [])
        if not values:
            continue
        lines.append(
            f"{domain_labels[domain]} & {len(values)} & "
            f"{statistics.median(values):.2f}\\% & "
            f"{statistics.fmean(values):.2f}\\% & "
            f"{max(values):.2f}\\% \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    (_TABLES_DIR / "tab_selector_regret.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = run()
    if not rows:
        raise SystemExit("no benchmark rows")
    if not all(bool(row["round_trip_ok"]) for row in rows):
        raise SystemExit("at least one round-trip failed")
    write_csv(rows)
    summary = summarize(rows)
    regrets = selector_regret(rows)
    write_tables(summary, regrets)
    print("Software benchmark complete.")


if __name__ == "__main__":
    main()
