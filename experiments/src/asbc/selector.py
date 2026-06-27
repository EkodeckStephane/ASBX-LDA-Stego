"""Interpretable block features and a lightweight deterministic selector."""

from __future__ import annotations

from dataclasses import dataclass

from .codec import Candidate, fixed_candidate
from .modes import Mode


@dataclass(frozen=True)
class BlockFeatures:
    length: int
    leading_zero_bytes: int
    trailing_zero_bytes: int
    nonzero_bytes: int
    one_bits: int
    one_runs: int

    @property
    def bit_length(self) -> int:
        return self.length * 8

    @property
    def zero_bits(self) -> int:
        return self.bit_length - self.one_bits

    @property
    def middle_bytes(self) -> int:
        return self.length - self.leading_zero_bytes - self.trailing_zero_bytes

    @property
    def zero_bytes(self) -> int:
        return self.length - self.nonzero_bytes


def block_features(block: bytes) -> BlockFeatures:
    left = 0
    while left < len(block) and block[left] == 0:
        left += 1
    right = len(block)
    while right > left and block[right - 1] == 0:
        right -= 1
    one_runs = 0
    previous = 0
    for value in block:
        for shift in range(7, -1, -1):
            current = (value >> shift) & 1
            if current and not previous:
                one_runs += 1
            previous = current
    return BlockFeatures(
        length=len(block),
        leading_zero_bytes=left,
        trailing_zero_bytes=len(block) - right,
        nonzero_bytes=sum(1 for value in block if value),
        one_bits=sum(value.bit_count() for value in block),
        one_runs=one_runs,
    )


def _varint_size(value: int) -> int:
    if value < 0:
        raise ValueError("varint size requires a non-negative value")
    size = 1
    while value >= 0x80:
        value >>= 7
        size += 1
    return size


def _average_gap_varint_size(bit_length: int, count: int) -> int:
    if count <= 0:
        return 0
    average_gap = max(1, bit_length // count)
    return _varint_size(average_gap)


def _record_cost(block_length: int, payload_cost: int) -> int:
    return 1 + _varint_size(block_length) + _varint_size(payload_cost) + payload_cost


def estimated_mode_costs(features: BlockFeatures) -> dict[Mode, int]:
    """Return cheap, interpretable complete-record cost estimates.

    These estimates deliberately avoid serialising every candidate payload.
    They use the same visible block features reported in the paper, so the
    selector can be explained and benchmarked against the exact oracle.
    """
    bit_length = features.bit_length
    one_gap_bytes = _average_gap_varint_size(bit_length, features.one_bits)
    zero_gap_bytes = _average_gap_varint_size(bit_length, features.zero_bits)

    costs = {
        Mode.RAW: _record_cost(features.length, features.length),
        Mode.ZERO_TRIM: _record_cost(
            features.length,
            _varint_size(features.leading_zero_bytes)
            + _varint_size(features.trailing_zero_bytes)
            + max(0, features.middle_bytes),
        ),
        Mode.ONE_GAPS: _record_cost(
            features.length,
            _varint_size(features.one_bits) + features.one_bits * one_gap_bytes,
        ),
        Mode.ZERO_GAPS: _record_cost(
            features.length,
            _varint_size(features.zero_bits) + features.zero_bits * zero_gap_bytes,
        ),
        Mode.ONE_RUNS: _record_cost(
            features.length,
            _varint_size(features.one_runs)
            + features.one_runs
            * (
                _average_gap_varint_size(bit_length, features.one_runs)
                + _average_gap_varint_size(max(1, features.one_bits), features.one_runs)
            ),
        ),
        Mode.NONZERO_BYTES: _record_cost(
            features.length,
            _varint_size(features.nonzero_bytes)
            + features.nonzero_bytes
            * (_average_gap_varint_size(features.length, features.nonzero_bytes) + 1),
        ),
    }
    if features.one_bits == 0:
        costs[Mode.ZERO] = _record_cost(features.length, 0)
    return costs


def deterministic_mode(block: bytes) -> Mode:
    features = block_features(block)
    costs = estimated_mode_costs(features)
    return min(costs, key=lambda mode: (costs[mode], int(mode)))


def deterministic_candidate(block: bytes) -> Candidate:
    return fixed_candidate(block, deterministic_mode(block))
