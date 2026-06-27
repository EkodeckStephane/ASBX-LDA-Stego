from __future__ import annotations

import csv
import io
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asbc.codec import candidates, fixed_candidate, oracle_candidate  # noqa: E402
from asbc.modes import Mode  # noqa: E402
from asbc.selector import block_features, deterministic_candidate  # noqa: E402
from asbc.varint import encode_uvarint  # noqa: E402

DATA = ROOT / "data" / "external"
RESULTS = ROOT / "results"
BLOCK_SIZE = 256
SEED = 20260609
MAX_TRAIN_BLOCKS = 40_000
MAX_VALIDATION_BLOCKS = 20_000


def longest_run(values: bytes, target_zero: bool) -> int:
    best = current = 0
    for value in values:
        matches = value == 0 if target_zero else value == 0xFF
        current = current + 1 if matches else 0
        best = max(best, current)
    return best


def features(block: bytes) -> list[float]:
    basic = block_features(block)
    array = np.frombuffer(block, dtype=np.uint8)
    if not len(array):
        return [0.0] * 17
    histogram, _ = np.histogram(array, bins=8, range=(0, 256))
    nonzero = int(np.count_nonzero(array))
    transitions = int(np.count_nonzero(array[1:] != array[:-1]))
    return [
        float(basic.length),
        float(basic.leading_zero_bytes),
        float(basic.trailing_zero_bytes),
        float(basic.middle_bytes),
        float(basic.one_bits),
        float(basic.zero_bits),
        float(basic.one_runs),
        float(nonzero),
        float(len(array) - nonzero),
        float(len(np.unique(array))),
        float(array.mean()),
        float(array.std()),
        float(transitions),
        float(longest_run(block, True)),
        float(longest_run(block, False)),
        *[float(value) for value in histogram],
    ]


def iter_files(split: str):
    matrix_split = split
    for path in sorted((DATA / "sparse_matrices" / matrix_split).glob("*.smb")):
        yield "sparse_matrix_pattern", "SuiteSparse_HB_bcsstk", path
    if split in {"train", "test"}:
        for dataset in ("mnist", "fashion_mnist"):
            for path in sorted(
                (DATA / "image_tensors" / dataset / split).glob("*.img")
            ):
                yield "grayscale_image_tensor", dataset, path


def split_training_files():
    all_files = list(iter_files("train"))
    train = []
    validation = []
    by_dataset = defaultdict(list)
    for item in all_files:
        by_dataset[item[1]].append(item)
    for dataset, items in by_dataset.items():
        if dataset == "SuiteSparse_HB_bcsstk":
            train.extend(items)
            continue
        boundary = max(1, int(len(items) * 0.8))
        train.extend(items[:boundary])
        validation.extend(items[boundary:])
    validation.extend(iter_files("validation"))
    return train, validation


def collect_blocks(files, sample_limit: int | None = None):
    raw_records = []
    for domain, dataset, path in files:
        data = path.read_bytes()
        for start in range(0, len(data), BLOCK_SIZE):
            block = data[start : start + BLOCK_SIZE]
            raw_records.append((domain, dataset, path.name, block))
    if sample_limit is not None and len(raw_records) > sample_limit:
        rng = np.random.default_rng(SEED)
        indices = rng.choice(len(raw_records), size=sample_limit, replace=False)
        raw_records = [raw_records[int(index)] for index in sorted(indices)]

    records = []
    for domain, dataset, file_name, block in raw_records:
        options = candidates(block)
        costs = {int(item.mode): item.serialized_bytes for item in options}
        oracle = min(options, key=lambda item: (item.serialized_bytes, int(item.mode)))
        ordered = sorted(item.serialized_bytes for item in options)
        margin = ordered[1] - ordered[0] if len(ordered) > 1 else 1
        rule = deterministic_candidate(block)
        records.append(
            (
                domain,
                dataset,
                file_name,
                features(block),
                int(oracle.mode),
                costs,
                max(1, margin),
                rule.serialized_bytes,
                len(block),
            )
        )
    return records


def model_bytes(model) -> int:
    buffer = io.BytesIO()
    joblib.dump(model, buffer, compress=3)
    return len(buffer.getvalue())


def stream_size(original_bytes: int, records: list[int]) -> int:
    raw = 4 + 1 + 1 + len(encode_uvarint(original_bytes)) + original_bytes
    adaptive = (
        4
        + 1
        + 1
        + len(encode_uvarint(original_bytes))
        + len(encode_uvarint(BLOCK_SIZE))
        + len(encode_uvarint(len(records)))
        + sum(records)
    )
    return min(raw, adaptive)


def evaluate(model_name: str, model, records):
    x = np.asarray([record[3] for record in records], dtype=np.float64)
    started = time.perf_counter()
    predictions = model.predict(x)
    inference_seconds = time.perf_counter() - started
    by_file = defaultdict(lambda: {"original": 0, "oracle": [], "selected": [], "rule": []})
    confusion = Counter()
    for record, prediction in zip(records, predictions):
        domain, dataset, file_name, _, label, costs, _, rule_cost, block_length = record
        raw_cost = costs[int(Mode.RAW)]
        selected_mode = int(prediction)
        selected_cost = min(costs.get(selected_mode, raw_cost), raw_cost)
        oracle_cost = min(costs.values())
        key = (domain, dataset, file_name)
        by_file[key]["original"] += block_length
        by_file[key]["oracle"].append(oracle_cost)
        by_file[key]["selected"].append(selected_cost)
        by_file[key]["rule"].append(rule_cost)
        effective_mode = selected_mode if costs.get(selected_mode, raw_cost) < raw_cost else int(Mode.RAW)
        confusion[(dataset, label, effective_mode)] += selected_cost - oracle_cost

    rows = []
    for (domain, dataset, file_name), values in sorted(by_file.items()):
        original = values["original"]
        oracle_size = stream_size(original, values["oracle"])
        selected_size = stream_size(original, values["selected"])
        rule_size = stream_size(original, values["rule"])
        rows.append(
            {
                "model": model_name,
                "domain": domain,
                "dataset": dataset,
                "file": file_name,
                "original_bytes": original,
                "oracle_bytes": oracle_size,
                "deterministic_bytes": rule_size,
                "selected_bytes": selected_size,
                "regret_bytes": selected_size - oracle_size,
                "improvement_vs_deterministic_bytes": rule_size - selected_size,
                "inference_seconds_share": inference_seconds / len(by_file),
            }
        )
    return rows, confusion, inference_seconds


def main() -> None:
    train_files, validation_files = split_training_files()
    train_records = collect_blocks(train_files, sample_limit=MAX_TRAIN_BLOCKS)
    validation_records = collect_blocks(
        validation_files, sample_limit=MAX_VALIDATION_BLOCKS
    )
    test_records = collect_blocks(list(iter_files("test")))

    x_train = np.asarray([record[3] for record in train_records], dtype=np.float64)
    y_train = np.asarray([record[4] for record in train_records], dtype=np.int64)
    weights = np.asarray([record[6] for record in train_records], dtype=np.float64)
    models = {
        "decision_tree": DecisionTreeClassifier(
            max_depth=10,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=SEED,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=120,
            max_leaf_nodes=31,
            learning_rate=0.08,
            l2_regularization=0.5,
            early_stopping=False,
            random_state=SEED,
        ),
        "small_mlp": make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(32, 16),
                alpha=1e-4,
                batch_size=512,
                learning_rate_init=1e-3,
                early_stopping=False,
                max_iter=100,
                random_state=SEED,
            ),
        ),
    }

    result_rows = []
    model_rows = []
    confusion_rows = []
    for name, model in models.items():
        started = time.perf_counter()
        model.fit(x_train, y_train, **({"sample_weight": weights} if name != "small_mlp" else {}))
        train_seconds = time.perf_counter() - started
        validation_rows, _, validation_inference = evaluate(
            name, model, validation_records
        )
        test_rows, confusion, test_inference = evaluate(name, model, test_records)
        result_rows.extend(test_rows)
        size = model_bytes(model)
        model_rows.append(
            {
                "model": name,
                "train_blocks": len(train_records),
                "validation_blocks": len(validation_records),
                "test_blocks": len(test_records),
                "feature_count": x_train.shape[1],
                "model_bytes": size,
                "train_seconds": train_seconds,
                "validation_inference_seconds": validation_inference,
                "test_inference_seconds": test_inference,
                "validation_regret_bytes": sum(
                    int(row["regret_bytes"]) for row in validation_rows
                ),
                "test_regret_bytes": sum(int(row["regret_bytes"]) for row in test_rows),
                "test_improvement_vs_deterministic_bytes": sum(
                    int(row["improvement_vs_deterministic_bytes"])
                    for row in test_rows
                ),
            }
        )
        for (dataset, oracle_mode, selected_mode), regret in confusion.items():
            confusion_rows.append(
                {
                    "model": name,
                    "dataset": dataset,
                    "oracle_mode": Mode(oracle_mode).name.lower(),
                    "selected_mode": Mode(selected_mode).name.lower(),
                    "regret_bytes": regret,
                }
            )
        print(f"Evaluated {name}: model={size} bytes")

    for path, rows in [
        (RESULTS / "ml_selector_files.csv", result_rows),
        (RESULTS / "ml_selector_models.csv", model_rows),
        (RESULTS / "ml_selector_confusion.csv", confusion_rows),
    ]:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print("Wrote ML selector evaluation artifacts")


if __name__ == "__main__":
    main()
