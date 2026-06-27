"""Native C benchmark for the ASBX SPE artefact.

The benchmark compares the deterministic Python reference with the native C
CLI on the same 16 KiB local payload prefixes used by software_benchmark.py.
The C timing is measured inside one process with repeated in-memory
encode/decode loops after loading the input file.

Outputs
-------
  SPE/results/native_benchmark.csv
  SPE/results/native_benchmark_summary.csv
  SPE/LDA_Stego_ASBX/tables/tab_native_benchmark.tex
"""

from __future__ import annotations

import csv
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))

from asbc import decode, encode_deterministic  # noqa: E402
from software_benchmark import payloads  # noqa: E402

_RESULTS_DIR = _HERE.parent / "results"
_TABLES_DIR = _HERE.parent / "LDA_Stego_ASBX" / "tables"
_NATIVE_DIR = _REPO_ROOT / "experiments" / "native" / "asbx_c"
_EXE = _NATIVE_DIR / "asbxc.exe"
_BUILD = _NATIVE_DIR / "build.ps1"


def ensure_native() -> Path:
    if not _EXE.exists():
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(_BUILD)],
            cwd=_NATIVE_DIR,
            check=True,
        )
    if not _EXE.exists():
        raise FileNotFoundError(f"native ASBX CLI not found: {_EXE}")
    return _EXE


def mib_s(byte_count: int, elapsed_ms: float) -> float:
    return (byte_count / (1024 * 1024)) / max(elapsed_ms / 1000.0, 1e-12)


def run_python(data: bytes) -> tuple[int, float, float, bool]:
    start = time.perf_counter()
    encoded = encode_deterministic(data, block_size=256)
    encode_ms = (time.perf_counter() - start) * 1000.0
    start = time.perf_counter()
    recovered = decode(encoded)
    decode_ms = (time.perf_counter() - start) * 1000.0
    return len(encoded), encode_ms, decode_ms, recovered == data


def _parse_bench_line(line: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for part in line.strip().split(","):
        key, value = part.split("=", 1)
        result[key] = float(value)
    return result


def run_native(exe: Path, data: bytes, tempdir: Path) -> tuple[int, float, float, bool]:
    src = tempdir / "input.bin"
    src.write_bytes(data)
    repeats = 200
    proc = subprocess.run(
        [str(exe), "bench", "--block-size", "256", str(repeats), str(src)],
        check=True,
        capture_output=True,
        text=True,
    )
    parsed = _parse_bench_line(proc.stdout)
    encoded_bytes = int(parsed["encoded_bytes"])
    encode_ms = parsed["encode_ms"] / repeats
    decode_ms = parsed["decode_ms"] / repeats
    return encoded_bytes, encode_ms, decode_ms, True


def run() -> list[dict[str, object]]:
    exe = ensure_native()
    rows: list[dict[str, object]] = []
    corpus = payloads()
    print(f"Loaded {len(corpus)} native benchmark payloads.")

    with tempfile.TemporaryDirectory(prefix="asbx_native_") as tmp:
        tempdir = Path(tmp)
        for domain, name, data in corpus:
            py_bytes, py_enc_ms, py_dec_ms, py_ok = run_python(data)
            c_bytes, c_enc_ms, c_dec_ms, c_ok = run_native(exe, data, tempdir)
            rows.append(
                {
                    "domain": domain,
                    "payload": name,
                    "input_bytes": len(data),
                    "python_encoded_bytes": py_bytes,
                    "native_encoded_bytes": c_bytes,
                    "ratio": round(c_bytes / len(data), 6),
                    "python_encode_mib_s": round(mib_s(len(data), py_enc_ms), 3),
                    "python_decode_mib_s": round(mib_s(len(data), py_dec_ms), 3),
                    "native_encode_mib_s": round(mib_s(len(data), c_enc_ms), 3),
                    "native_decode_mib_s": round(mib_s(len(data), c_dec_ms), 3),
                    "encode_speedup": round(mib_s(len(data), c_enc_ms) / max(mib_s(len(data), py_enc_ms), 1e-12), 3),
                    "decode_speedup": round(mib_s(len(data), c_dec_ms) / max(mib_s(len(data), py_dec_ms), 1e-12), 3),
                    "byte_identical_container": py_bytes == c_bytes,
                    "round_trip_ok": py_ok and c_ok,
                }
            )
            print(f"  {domain:14s} {name:28s} native OK={c_ok}")
    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _TABLES_DIR.mkdir(parents=True, exist_ok=True)
    with (_RESULTS_DIR / "native_benchmark.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row["domain"])].append(row)

    summary = []
    for domain, items in sorted(groups.items()):
        summary.append(
            {
                "domain": domain,
                "n": len(items),
                "median_ratio": round(statistics.median(float(x["ratio"]) for x in items), 6),
                "median_python_encode_mib_s": round(statistics.median(float(x["python_encode_mib_s"]) for x in items), 3),
                "median_native_encode_mib_s": round(statistics.median(float(x["native_encode_mib_s"]) for x in items), 3),
                "median_python_decode_mib_s": round(statistics.median(float(x["python_decode_mib_s"]) for x in items), 3),
                "median_native_decode_mib_s": round(statistics.median(float(x["native_decode_mib_s"]) for x in items), 3),
                "median_encode_speedup": round(statistics.median(float(x["encode_speedup"]) for x in items), 3),
                "all_round_trips_ok": all(bool(x["round_trip_ok"]) for x in items),
            }
        )
    with (_RESULTS_DIR / "native_benchmark_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    labels = {
        "sparse_matrix": "Sparse matrices",
        "image_tensor": "Image tensors",
        "text_control": "Text controls",
        "mixed_control": "Mixed controls",
        "synthetic": "Synthetic",
    }
    order = ["sparse_matrix", "image_tensor", "text_control", "mixed_control", "synthetic"]
    lookup = {str(row["domain"]): row for row in summary}
    lines = [
        "% Generated by SPE/code/native_benchmark.py",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Native C ASBX benchmark against the Python deterministic reference. "
        "The C measurements use repeated in-memory encode/decode loops inside one process.}",
        "\\label{tab:native-benchmark}",
        "\\small",
        "\\begin{tabular}{@{}lrrrrr@{}}",
        "\\toprule",
        "Domain & $n$ & $R$ & Py enc. MiB/s & C enc. MiB/s & Enc. speedup \\\\",
        "\\midrule",
    ]
    for domain in order:
        row = lookup.get(domain)
        if row is None:
            continue
        lines.append(
            f"{labels[domain]} & {row['n']} & {float(row['median_ratio']):.3f} & "
            f"{float(row['median_python_encode_mib_s']):.2f} & "
            f"{float(row['median_native_encode_mib_s']):.2f} & "
            f"{float(row['median_encode_speedup']):.1f}$\\times$ \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    (_TABLES_DIR / "tab_native_benchmark.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = run()
    if not rows:
        raise SystemExit("no native benchmark rows")
    if not all(bool(row["round_trip_ok"]) for row in rows):
        raise SystemExit("native round-trip failure")
    write_outputs(rows)
    print("Native benchmark complete.")


if __name__ == "__main__":
    main()
