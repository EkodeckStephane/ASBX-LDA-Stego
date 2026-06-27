from asbc import decode, encode_deterministic
from asbc.modes import Mode
from asbc.selector import block_features, deterministic_mode, estimated_mode_costs


def test_block_features() -> None:
    features = block_features(b"\x00\x00\x01\x80\x00")
    assert features.leading_zero_bytes == 2
    assert features.trailing_zero_bytes == 1
    assert features.nonzero_bytes == 2
    assert features.one_bits == 2
    assert features.zero_bits == 38
    assert features.one_runs == 1
    assert features.middle_bytes == 2


def test_deterministic_mode_extremes() -> None:
    assert deterministic_mode(bytes(64)) is Mode.ZERO
    assert deterministic_mode(b"\xff" * 64) is Mode.ZERO_GAPS
    assert deterministic_mode(b"\x00" * 20 + b"data" + b"\x00" * 20) is Mode.ZERO_TRIM
    assert deterministic_mode(bytes(range(64))) is Mode.RAW


def test_estimated_costs_include_extended_modes() -> None:
    block = b"\x00" * 60 + b"\x01\x80\x03\x04"
    costs = estimated_mode_costs(block_features(block))
    assert Mode.ONE_RUNS in costs
    assert Mode.NONZERO_BYTES in costs
    assert costs[Mode.ZERO_TRIM] < costs[Mode.RAW]


def test_deterministic_mode_uses_nonzero_byte_sparse_case() -> None:
    block = bytearray(256)
    block[10] = 17
    block[100] = 99
    block[200] = 7
    assert deterministic_mode(bytes(block)) is Mode.NONZERO_BYTES


def test_deterministic_mode_uses_one_runs_for_dense_runs() -> None:
    block = b"\xff" * 16 + b"\x00" * 112
    assert deterministic_mode(block) is Mode.ONE_RUNS


def test_deterministic_encode_round_trip() -> None:
    samples = [
        bytes(256),
        b"\xff" * 256,
        b"\x00" * 60 + b"payload" + b"\x00" * 60,
        bytes(range(256)),
    ]
    for sample in samples:
        assert decode(encode_deterministic(sample, block_size=64)) == sample
