import itertools

import pytest

from asbc.modes import Mode, applicable_modes, decode_payload, encode_payload


@pytest.mark.parametrize(
    "block",
    [
        b"",
        b"\x00",
        b"\xff",
        b"\x00\x00\x01\x00",
        b"\xff\xff\xfe\xff",
        bytes(range(256)),
    ],
)
def test_all_applicable_modes_roundtrip(block: bytes) -> None:
    for mode in applicable_modes(block):
        assert decode_payload(mode, encode_payload(mode, block), len(block)) == block


def test_exhaustive_one_byte_roundtrip() -> None:
    for value in range(256):
        block = bytes([value])
        for mode in applicable_modes(block):
            assert decode_payload(mode, encode_payload(mode, block), 1) == block


def test_exhaustive_two_byte_positional_roundtrip() -> None:
    for left, right in itertools.product(range(16), repeat=2):
        block = bytes([left, right])
        for mode in (Mode.ONE_GAPS, Mode.ZERO_GAPS):
            assert decode_payload(mode, encode_payload(mode, block), 2) == block


def test_zero_mode_rejects_nonzero_block() -> None:
    with pytest.raises(ValueError):
        encode_payload(Mode.ZERO, b"\x01")


def test_invalid_position_gap_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        decode_payload(Mode.ONE_GAPS, b"\x01\x00", 1)


@pytest.mark.parametrize(
    "block",
    [
        b"\x00" * 32,
        b"\xff" * 32,
        b"\x00\x0f\xf0\x00",
        b"\x00A\x00B\x00\x00C",
        bytes(range(64)),
    ],
)
@pytest.mark.parametrize("mode", [Mode.ONE_RUNS, Mode.NONZERO_BYTES])
def test_structural_modes_roundtrip(block: bytes, mode: Mode) -> None:
    assert decode_payload(mode, encode_payload(mode, block), len(block)) == block
