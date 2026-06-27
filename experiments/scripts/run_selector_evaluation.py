from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import decode, encode, encode_fixed, encode_with_selector  # noqa: E402
from asbc.modes import Mode  # noqa: E402
from asbc.selector import deterministic_candidate  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "reference.json").read_text(encoding="utf-8"))
DATA = ROOT / "data" / "synthetic"
RESULTS = ROOT / "results"


def timed_encode(method, source: bytes) -> tuple[bytes, float]:
    started = time.perf_counter()
    container = method(source)
    return container, time.perf_counter() - started


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    block_size = int(CONFIG["selector_block_size"])
    methods = {
        "oracle": lambda data: encode(data, block_size),
        "deterministic": lambda data: encode_with_selector(
            data, block_size, deterministic_candidate
        ),
        **{
            f"fixed_{mode.name.lower()}": (
                lambda data, selected=mode: encode_fixed(data, selected, block_size)
            )
            for mode in Mode
        },
    }

    rows = []
    for split in CONFIG["synthetic_splits"]:
        for path in sorted((DATA / split).glob("*.bin")):
            source = path.read_bytes()
            for method_name, method in methods.items():
                container, encode_seconds = timed_encode(method, source)
                started = time.perf_counter()
                restored = decode(container)
                decode_seconds = time.perf_counter() - started
                if restored != source:
                    raise RuntimeError(f"round-trip mismatch: {split}/{path.name}/{method_name}")
                rows.append(
                    {
                        "split": split,
                        "scenario": path.stem,
                        "file": path.name,
                        "method": method_name,
                        "block_size": block_size,
                        "original_bytes": len(source),
                        "encoded_bytes": len(container),
                        "ratio": len(container) / len(source),
                        "encode_seconds": encode_seconds,
                        "decode_seconds": decode_seconds,
                    }
                )

    measurements = RESULTS / "selector_measurements.csv"
    with measurements.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lookup = {
        (row["split"], row["scenario"], row["method"]): row
        for row in rows
    }
    fixed_methods = [name for name in methods if name.startswith("fixed_")]
    global_train_bytes = {
        method: sum(
            int(row["encoded_bytes"])
            for row in rows
            if row["split"] == "train" and row["method"] == method
        )
        for method in fixed_methods
    }
    global_best = min(global_train_bytes, key=global_train_bytes.get)

    summary_rows = []
    for scenario in sorted({row["scenario"] for row in rows}):
        scenario_best = min(
            fixed_methods,
            key=lambda method: int(
                lookup[("train", scenario, method)]["encoded_bytes"]
            ),
        )
        oracle = lookup[("test", scenario, "oracle")]
        deterministic = lookup[("test", scenario, "deterministic")]
        best_fixed = lookup[("test", scenario, scenario_best)]
        global_fixed = lookup[("test", scenario, global_best)]
        original = int(oracle["original_bytes"])
        oracle_bytes = int(oracle["encoded_bytes"])
        deterministic_bytes = int(deterministic["encoded_bytes"])
        summary_rows.append(
            {
                "scenario": scenario,
                "original_bytes": original,
                "oracle_bytes": oracle_bytes,
                "oracle_ratio": oracle_bytes / original,
                "deterministic_bytes": deterministic_bytes,
                "deterministic_ratio": deterministic_bytes / original,
                "deterministic_regret_bytes": deterministic_bytes - oracle_bytes,
                "deterministic_regret_fraction": (
                    deterministic_bytes - oracle_bytes
                )
                / original,
                "train_selected_fixed": scenario_best,
                "selected_fixed_test_bytes": int(best_fixed["encoded_bytes"]),
                "selected_fixed_test_ratio": int(best_fixed["encoded_bytes"]) / original,
                "global_train_fixed": global_best,
                "global_fixed_test_bytes": int(global_fixed["encoded_bytes"]),
                "global_fixed_test_ratio": int(global_fixed["encoded_bytes"]) / original,
            }
        )

    summary = RESULTS / "selector_test_summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(
        f"Wrote {len(rows)} measurements and {len(summary_rows)} held-out summaries"
    )


if __name__ == "__main__":
    main()

