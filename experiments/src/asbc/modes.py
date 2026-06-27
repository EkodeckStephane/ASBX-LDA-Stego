"""Elementary exactly decodable block representations."""

from __future__ import annotations

from enum import IntEnum

from .varint import decode_uvarint, encode_uvarint


class Mode(IntEnum):
    RAW = 0
    ZERO = 1
    ZERO_TRIM = 2
    ONE_GAPS = 3
    ZERO_GAPS = 4
    ONE_RUNS = 5
    NONZERO_BYTES = 6


def encode_payload(mode: Mode, block: bytes) -> bytes:
    if mode is Mode.RAW:
        return block
    if mode is Mode.ZERO:
        if any(block):
            raise ValueError("zero mode requires an all-zero block")
        return b""
    if mode is Mode.ZERO_TRIM:
        left = 0
        while left < len(block) and block[left] == 0:
            left += 1
        right = len(block)
        while right > left and block[right - 1] == 0:
            right -= 1
        return (
            encode_uvarint(left)
            + encode_uvarint(len(block) - right)
            + block[left:right]
        )
    if mode is Mode.ONE_GAPS:
        return _encode_positions(block, target=1)
    if mode is Mode.ZERO_GAPS:
        return _encode_positions(block, target=0)
    if mode is Mode.ONE_RUNS:
        return _encode_one_runs(block)
    if mode is Mode.NONZERO_BYTES:
        return _encode_nonzero_bytes(block)
    raise ValueError("unsupported mode")


def decode_payload(mode: Mode, payload: bytes, block_length: int) -> bytes:
    if block_length < 0:
        raise ValueError("negative block length")
    if mode is Mode.RAW:
        if len(payload) != block_length:
            raise ValueError("raw payload length mismatch")
        return payload
    if mode is Mode.ZERO:
        if payload:
            raise ValueError("zero payload must be empty")
        return bytes(block_length)
    if mode is Mode.ZERO_TRIM:
        left, offset = decode_uvarint(payload)
        right, offset = decode_uvarint(payload, offset)
        middle = payload[offset:]
        if left + len(middle) + right != block_length:
            raise ValueError("trimmed block length mismatch")
        if middle and (middle[0] == 0 or middle[-1] == 0):
            raise ValueError("non-canonical zero-trim payload")
        return bytes(left) + middle + bytes(right)
    if mode is Mode.ONE_GAPS:
        return _decode_positions(payload, block_length, target=1)
    if mode is Mode.ZERO_GAPS:
        return _decode_positions(payload, block_length, target=0)
    if mode is Mode.ONE_RUNS:
        return _decode_one_runs(payload, block_length)
    if mode is Mode.NONZERO_BYTES:
        return _decode_nonzero_bytes(payload, block_length)
    raise ValueError("unsupported mode")


def applicable_modes(block: bytes) -> tuple[Mode, ...]:
    modes = [
        Mode.RAW,
        Mode.ZERO_TRIM,
        Mode.ONE_GAPS,
        Mode.ZERO_GAPS,
        Mode.ONE_RUNS,
        Mode.NONZERO_BYTES,
    ]
    if not any(block):
        modes.append(Mode.ZERO)
    return tuple(modes)


def _bit_positions(block: bytes, target: int) -> list[int]:
    positions = []
    for byte_index, value in enumerate(block):
        for bit_index in range(8):
            bit = (value >> (7 - bit_index)) & 1
            if bit == target:
                positions.append(byte_index * 8 + bit_index)
    return positions


def _encode_positions(block: bytes, target: int) -> bytes:
    positions = _bit_positions(block, target)
    output = bytearray(encode_uvarint(len(positions)))
    previous = -1
    for position in positions:
        gap = position - previous
        output += encode_uvarint(gap)
        previous = position
    return bytes(output)


def _decode_positions(payload: bytes, block_length: int, target: int) -> bytes:
    count, offset = decode_uvarint(payload)
    bit_length = block_length * 8
    if count > bit_length:
        raise ValueError("position count exceeds block bit length")
    positions = []
    previous = -1
    for _ in range(count):
        gap, offset = decode_uvarint(payload, offset)
        if gap <= 0:
            raise ValueError("position gaps must be positive")
        position = previous + gap
        if position >= bit_length:
            raise ValueError("bit position out of range")
        positions.append(position)
        previous = position
    if offset != len(payload):
        raise ValueError("trailing position payload bytes")

    fill = 0xFF if target == 0 else 0x00
    output = bytearray([fill] * block_length)
    for position in positions:
        byte_index, bit_index = divmod(position, 8)
        mask = 1 << (7 - bit_index)
        if target == 1:
            output[byte_index] |= mask
        else:
            output[byte_index] &= ~mask
    return bytes(output)


def _one_runs(block: bytes) -> list[tuple[int, int]]:
    runs = []
    start = None
    bit_length = len(block) * 8
    for position in range(bit_length):
        byte_index, bit_index = divmod(position, 8)
        active = bool(block[byte_index] & (1 << (7 - bit_index)))
        if active and start is None:
            start = position
        elif not active and start is not None:
            runs.append((start, position - start))
            start = None
    if start is not None:
        runs.append((start, bit_length - start))
    return runs


def _encode_one_runs(block: bytes) -> bytes:
    runs = _one_runs(block)
    output = bytearray(encode_uvarint(len(runs)))
    previous_end = 0
    for start, length in runs:
        output += encode_uvarint(start - previous_end)
        output += encode_uvarint(length)
        previous_end = start + length
    return bytes(output)


def _decode_one_runs(payload: bytes, block_length: int) -> bytes:
    count, offset = decode_uvarint(payload)
    bit_length = block_length * 8
    output = bytearray(block_length)
    previous_end = 0
    for _ in range(count):
        zero_gap, offset = decode_uvarint(payload, offset)
        run_length, offset = decode_uvarint(payload, offset)
        if run_length <= 0:
            raise ValueError("one run length must be positive")
        start = previous_end + zero_gap
        end = start + run_length
        if start < previous_end or end > bit_length:
            raise ValueError("one run out of range")
        for position in range(start, end):
            byte_index, bit_index = divmod(position, 8)
            output[byte_index] |= 1 << (7 - bit_index)
        previous_end = end
    if offset != len(payload):
        raise ValueError("trailing one-run payload bytes")
    return bytes(output)


def _encode_nonzero_bytes(block: bytes) -> bytes:
    items = [(index, value) for index, value in enumerate(block) if value]
    output = bytearray(encode_uvarint(len(items)))
    previous = -1
    for position, value in items:
        output += encode_uvarint(position - previous)
        output.append(value)
        previous = position
    return bytes(output)


def _decode_nonzero_bytes(payload: bytes, block_length: int) -> bytes:
    count, offset = decode_uvarint(payload)
    if count > block_length:
        raise ValueError("nonzero byte count exceeds block length")
    output = bytearray(block_length)
    previous = -1
    for _ in range(count):
        gap, offset = decode_uvarint(payload, offset)
        if gap <= 0:
            raise ValueError("nonzero byte gaps must be positive")
        position = previous + gap
        if position >= block_length or offset >= len(payload):
            raise ValueError("nonzero byte entry out of range")
        value = payload[offset]
        offset += 1
        if value == 0:
            raise ValueError("nonzero byte entry cannot store zero")
        output[position] = value
        previous = position
    if offset != len(payload):
        raise ValueError("trailing nonzero-byte payload bytes")
    return bytes(output)
