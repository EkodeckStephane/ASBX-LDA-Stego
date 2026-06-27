import pytest

from asbc.varint import decode_uvarint, encode_uvarint


@pytest.mark.parametrize("value", [0, 1, 127, 128, 255, 16384, 2**32, 2**63 - 1])
def test_uvarint_roundtrip(value: int) -> None:
    encoded = encode_uvarint(value)
    assert decode_uvarint(encoded) == (value, len(encoded))


def test_noncanonical_uvarint_rejected() -> None:
    with pytest.raises(ValueError, match="non-canonical"):
        decode_uvarint(b"\x80\x00")


def test_truncated_uvarint_rejected() -> None:
    with pytest.raises(ValueError, match="truncated"):
        decode_uvarint(b"\x80")

