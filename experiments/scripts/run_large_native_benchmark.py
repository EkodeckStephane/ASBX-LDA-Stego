from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "asbx_c"
EXE = NATIVE / "asbxc.exe"
BUILD = NATIVE / "build.ps1"
CORPUS = ROOT / "data" / "generated_large"
OUTPUT = ROOT / "results" / "native_large_benchmark.csv"


def ensure_native() -> Path:
    if not EXE.exists():
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            cwd=NATIVE,
            check=True,
        )
    if not EXE.exists():
        raise FileNotFoundError(f"native ASBX CLI not found: {EXE}")
    return EXE


def parse(line: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in line.strip().split(","):
        key, value = item.split("=", 1)
        values[key] = float(value)
    return values


def mib_s(byte_count: int, elapsed_ms: float) -> float:
    return (byte_count / (1024 * 1024)) / max(elapsed_ms / 1000.0, 1e-12)


def main() -> None:
    if not CORPUS.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_large_corpus.py")], check=True)

    exe = ensure_native()
    rows = []
    for path in sorted(CORPUS.glob("*.bin")):
        proc = subprocess.run(
            [str(exe), "bench", "--block-size", "256", "30", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        values = parse(proc.stdout)
        repeats = int(values["repeats"])
        input_bytes = int(values["input_bytes"])
        encoded_bytes = int(values["encoded_bytes"])
        encode_ms = values["encode_ms"] / repeats
        decode_ms = values["decode_ms"] / repeats
        rows.append(
            {
                "file": path.name,
                "input_bytes": input_bytes,
                "encoded_bytes": encoded_bytes,
                "ratio": round(encoded_bytes / input_bytes, 6),
                "encode_mib_s": round(mib_s(input_bytes, encode_ms), 3),
                "decode_mib_s": round(mib_s(input_bytes, decode_ms), 3),
                "repeats": repeats,
            }
        )
        print(f"{path.name}: ratio={rows[-1]['ratio']} encode={rows[-1]['encode_mib_s']} MiB/s")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
