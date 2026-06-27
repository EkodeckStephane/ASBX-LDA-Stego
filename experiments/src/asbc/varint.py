"""Canonical unsigned LEB128 encoding."""

from __future__ import annotations


def encode_uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("uvarint cannot encode a negative value")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        output.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(output)


def decode_uvarint(data: bytes, offset: int = 0) -> tuple[int, int]:
    start = offset
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if data[start:offset] != encode_uvarint(value):
                raise ValueError("non-canonical uvarint")
            return value, offset
        shift += 7
        if shift > 63:
            raise ValueError("uvarint exceeds supported range")
    raise ValueError("truncated uvarint")

