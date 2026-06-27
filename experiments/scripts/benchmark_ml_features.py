from __future__ import annotations

import csv
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.selector import deterministic_mode  # noqa: E402


def load_evaluation_module():
    path = ROOT / "scripts" / "evaluate_ml_selector.py"
    spec = importlib.util.spec_from_file_location("ml_selector_evaluation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load ML evaluation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_evaluation_module()
    blocks = []
    for _, _, path in module.iter_files("test"):
        data = path.read_bytes()
        blocks.extend(
            data[start : start + module.BLOCK_SIZE]
            for start in range(0, len(data), module.BLOCK_SIZE)
        )

    started = time.perf_counter()
    for block in blocks:
        deterministic_mode(block)
    deterministic_seconds = time.perf_counter() - started

    started = time.perf_counter()
    for block in blocks:
        module.features(block)
    ml_seconds = time.perf_counter() - started

    rows = [
        {
            "method": "deterministic_features",
            "blocks": len(blocks),
            "seconds": deterministic_seconds,
            "microseconds_per_block": deterministic_seconds / len(blocks) * 1e6,
        },
        {
            "method": "ml_features",
            "blocks": len(blocks),
            "seconds": ml_seconds,
            "microseconds_per_block": ml_seconds / len(blocks) * 1e6,
        },
    ]
    output = ROOT / "results" / "ml_feature_timing.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote ML feature timing for {len(blocks)} held-out blocks")


if __name__ == "__main__":
    main()

