"""Complete, exactly decodable baselines for selected sparse domains."""

from __future__ import annotations

import io
import struct

from PIL import Image

from .varint import decode_uvarint, encode_uvarint


def encode_sparse_positions(data: bytes) -> bytes:
    if not data.startswith(b"SMB1") or len(data) < 28:
        raise ValueError("invalid sparse matrix bitmap")
    rows, cols, declared = struct.unpack(">QQQ", data[4:28])
    positions = []
    for byte_index, value in enumerate(data[28:]):
        for bit_index in range(8):
            position = byte_index * 8 + bit_index
            if position >= rows * cols:
                break
            if value & (1 << (7 - bit_index)):
                positions.append(position)
    if len(positions) != declared:
        raise ValueError("sparse matrix nonzero count mismatch")
    output = bytearray(b"SPG1")
    output += encode_uvarint(rows)
    output += encode_uvarint(cols)
    output += encode_uvarint(len(positions))
    previous = -1
    for position in positions:
        output += encode_uvarint(position - previous)
        previous = position
    return bytes(output)


def decode_sparse_positions(data: bytes) -> bytes:
    if not data.startswith(b"SPG1"):
        raise ValueError("invalid sparse position magic")
    rows, offset = decode_uvarint(data, 4)
    cols, offset = decode_uvarint(data, offset)
    count, offset = decode_uvarint(data, offset)
    bitmap = bytearray((rows * cols + 7) // 8)
    previous = -1
    for _ in range(count):
        gap, offset = decode_uvarint(data, offset)
        if gap <= 0:
            raise ValueError("invalid sparse position gap")
        position = previous + gap
        if position >= rows * cols:
            raise ValueError("sparse position out of range")
        byte_index, bit_index = divmod(position, 8)
        bitmap[byte_index] |= 1 << (7 - bit_index)
        previous = position
    if offset != len(data):
        raise ValueError("trailing sparse position bytes")
    return b"SMB1" + struct.pack(">QQQ", rows, cols, count) + bytes(bitmap)


def encode_png_images(data: bytes) -> bytes:
    if not data.startswith(b"IMG1") or len(data) < 16:
        raise ValueError("invalid image tensor")
    count, rows, cols = struct.unpack(">III", data[4:16])
    pixels = data[16:]
    image_bytes = rows * cols
    if len(pixels) != count * image_bytes:
        raise ValueError("image tensor length mismatch")
    output = bytearray(b"PNGS")
    output += encode_uvarint(count)
    output += encode_uvarint(rows)
    output += encode_uvarint(cols)
    for index in range(count):
        start = index * image_bytes
        image = Image.frombytes("L", (cols, rows), pixels[start : start + image_bytes])
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=False, compress_level=9)
        payload = buffer.getvalue()
        output += encode_uvarint(len(payload))
        output += payload
    return bytes(output)


def decode_png_images(data: bytes) -> bytes:
    if not data.startswith(b"PNGS"):
        raise ValueError("invalid PNG sequence magic")
    count, offset = decode_uvarint(data, 4)
    rows, offset = decode_uvarint(data, offset)
    cols, offset = decode_uvarint(data, offset)
    pixels = bytearray()
    for _ in range(count):
        length, offset = decode_uvarint(data, offset)
        payload = data[offset : offset + length]
        if len(payload) != length:
            raise ValueError("truncated PNG image")
        offset += length
        with Image.open(io.BytesIO(payload)) as image:
            if image.mode != "L" or image.size != (cols, rows):
                raise ValueError("unexpected PNG image format")
            pixels += image.tobytes()
    if offset != len(data):
        raise ValueError("trailing PNG sequence bytes")
    return b"IMG1" + struct.pack(">III", count, rows, cols) + bytes(pixels)

