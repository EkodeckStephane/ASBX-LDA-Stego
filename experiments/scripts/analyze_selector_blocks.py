from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import oracle_candidate  # noqa: E402
from asbc.selector import deterministic_candidate  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "reference.json").read_text(encoding="utf-8"))
DATA = ROOT / "data" / "synthetic" / "test"
RESULTS = ROOT / "results"


def main() -> None:
    block_size = int(CONFIG["selector_block_size"])
    aggregates: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"blocks": 0, "regret_bytes": 0}
    )
    for path in sorted(DATA.glob("*.bin")):
        source = path.read_bytes()
        for start in range(0, len(source), block_size):
            block = source[start : start + block_size]
            oracle = oracle_candidate(block)
            selected = deterministic_candidate(block)
            key = (path.stem, oracle.mode.name.lower(), selected.mode.name.lower())
            aggregates[key]["blocks"] += 1
            aggregates[key]["regret_bytes"] += (
                selected.serialized_bytes - oracle.serialized_bytes
            )

    rows = [
        {
            "scenario": scenario,
            "oracle_mode": oracle_mode,
            "selected_mode": selected_mode,
            "blocks": values["blocks"],
            "regret_bytes": values["regret_bytes"],
        }
        for (scenario, oracle_mode, selected_mode), values in sorted(aggregates.items())
    ]
    output = RESULTS / "selector_block_confusion.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} selector confusion rows to {output}")


if __name__ == "__main__":
    main()

