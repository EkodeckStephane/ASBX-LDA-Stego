import os

import pytest

from asbc.codec import (
    MAGIC,
    STREAM_RAW,
    VERSION,
    candidates,
    decode,
    encode,
    encode_fixed,
    encode_with_selector,
    fixed_candidate,
    oracle_candidate,
)
from asbc.modes import Mode
from asbc.selector import deterministic_candidate


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00",
        b"\x00" * 4096,
        b"\xff" * 4096,
        b"\x00" * 200 + b"payload" + b"\x00" * 300,
        bytes(range(256)) * 4,
        os.urandom(4096),
    ],
)
@pytest.mark.parametrize("block_size", [1, 7, 16, 64, 256])
def test_stream_roundtrip(data: bytes, block_size: int) -> None:
    assert decode(encode(data, block_size)) == data


@pytest.mark.parametrize(
    "block",
    [b"", b"\x00" * 32, b"\xff" * 32, b"\x00\x01\x00", bytes(range(32))],
)
def test_oracle_uses_shortest_complete_record(block: bytes) -> None:
    selected = oracle_candidate(block)
    all_candidates = candidates(block)
    assert selected.serialized_bytes == min(item.serialized_bytes for item in all_candidates)
    assert selected.record in {item.record for item in all_candidates}


def test_zero_block_selects_zero_mode() -> None:
    assert oracle_candidate(bytes(256)).mode is Mode.ZERO


@pytest.mark.parametrize("mode", list(Mode))
def test_fixed_mode_stream_roundtrip(mode: Mode) -> None:
    data = b"\x00" * 100 + bytes(range(256)) + b"\xff" * 100
    assert decode(encode_fixed(data, mode, block_size=64)) == data


def test_fixed_candidate_falls_back_to_raw() -> None:
    block = bytes(range(64))
    assert fixed_candidate(block, Mode.ZERO).mode is Mode.RAW


def test_deterministic_selector_stream_roundtrip() -> None:
    data = b"\x00" * 1024 + b"\xff" * 1024 + bytes(range(256))
    container = encode_with_selector(data, 128, deterministic_candidate)
    assert decode(container) == data


def test_magic_and_version() -> None:
    assert encode(b"test").startswith(MAGIC + bytes([VERSION]))


def test_incompressible_stream_uses_global_raw_fallback() -> None:
    data = bytes(range(256)) * 4
    container = encode(data, block_size=64)
    assert container[len(MAGIC) + 1] == STREAM_RAW
    assert decode(container) == data


@pytest.mark.parametrize(
    "container",
    [
        b"",
        b"NOPE",
        MAGIC,
        MAGIC + b"\x01",
        MAGIC + bytes([VERSION, 0]),
    ],
)
def test_malformed_stream_rejected(container: bytes) -> None:
    with pytest.raises(ValueError):
        decode(container)


def test_trailing_bytes_rejected() -> None:
    with pytest.raises(ValueError):
        decode(encode(b"abc") + b"\x00")


def test_truncated_payload_rejected() -> None:
    container = encode(bytes(range(64)), block_size=64)
    with pytest.raises(ValueError):
        decode(container[:-1])
