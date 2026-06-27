from asbc.domain_baselines import (
    decode_png_images,
    decode_sparse_positions,
    encode_png_images,
    encode_sparse_positions,
)


def test_sparse_positions_roundtrip() -> None:
    source = b"SMB1" + (3).to_bytes(8, "big") + (5).to_bytes(8, "big")
    source += (3).to_bytes(8, "big") + bytes([0b10001000, 0b00000010])
    assert decode_sparse_positions(encode_sparse_positions(source)) == source


def test_png_images_roundtrip() -> None:
    pixels = bytes(range(16)) + bytes(reversed(range(16)))
    source = b"IMG1" + (2).to_bytes(4, "big")
    source += (4).to_bytes(4, "big") + (4).to_bytes(4, "big") + pixels
    assert decode_png_images(encode_png_images(source)) == source
