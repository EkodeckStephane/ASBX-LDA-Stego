"""Experimental ASBX stream and exact per-block serialization oracle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .modes import Mode, applicable_modes, decode_payload, encode_payload
from .varint import decode_uvarint, encode_uvarint

MAGIC = b"ASBX"
VERSION = 0
STREAM_RAW = 0
STREAM_BLOCKS = 1


@dataclass(frozen=True)
class Candidate:
    mode: Mode
    payload: bytes
    record: bytes

    @property
    def serialized_bytes(self) -> int:
        return len(self.record)


def serialize_record(mode: Mode, block: bytes) -> bytes:
    payload = encode_payload(mode, block)
    return (
        bytes([mode])
        + encode_uvarint(len(block))
        + encode_uvarint(len(payload))
        + payload
    )


def candidates(block: bytes) -> tuple[Candidate, ...]:
    result = []
    for mode in applicable_modes(block):
        payload = encode_payload(mode, block)
        record = (
            bytes([mode])
            + encode_uvarint(len(block))
            + encode_uvarint(len(payload))
            + payload
        )
        result.append(Candidate(mode, payload, record))
    return tuple(result)


def oracle_candidate(block: bytes) -> Candidate:
    return min(candidates(block), key=lambda item: (len(item.record), int(item.mode)))


def fixed_candidate(block: bytes, mode: Mode) -> Candidate:
    raw = _candidate(Mode.RAW, block)
    if mode not in applicable_modes(block):
        return raw
    selected = _candidate(mode, block)
    return selected if len(selected.record) < len(raw.record) else raw


def encode_with_selector(
    data: bytes,
    block_size: int,
    selector: Callable[[bytes], Candidate],
) -> bytes:
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    blocks = [data[start : start + block_size] for start in range(0, len(data), block_size)]
    prefix = MAGIC + bytes([VERSION])
    raw = prefix + bytes([STREAM_RAW]) + encode_uvarint(len(data)) + data
    output = bytearray(prefix)
    output.append(STREAM_BLOCKS)
    output += encode_uvarint(len(data))
    output += encode_uvarint(block_size)
    output += encode_uvarint(len(blocks))
    for block in blocks:
        selected = selector(block)
        if decode_payload(selected.mode, selected.payload, len(block)) != block:
            raise ValueError("selector returned a non-round-tripping candidate")
        output += selected.record
    adaptive = bytes(output)
    return adaptive if len(adaptive) < len(raw) else raw


def encode(data: bytes, block_size: int = 256) -> bytes:
    return encode_with_selector(data, block_size, oracle_candidate)


def encode_deterministic(data: bytes, block_size: int = 256) -> bytes:
    from .selector import deterministic_candidate

    return encode_with_selector(data, block_size, deterministic_candidate)


def encode_fixed(data: bytes, mode: Mode, block_size: int = 256) -> bytes:
    return encode_with_selector(
        data,
        block_size,
        lambda block: fixed_candidate(block, mode),
    )


def _candidate(mode: Mode, block: bytes) -> Candidate:
    payload = encode_payload(mode, block)
    return Candidate(mode, payload, serialize_record(mode, block))


def decode(container: bytes) -> bytes:
    if not container.startswith(MAGIC):
        raise ValueError("invalid ASBX magic")
    offset = len(MAGIC)
    if offset >= len(container) or container[offset] != VERSION:
        raise ValueError("unsupported ASBX version")
    offset += 1
    if offset >= len(container):
        raise ValueError("truncated stream mode")
    stream_mode = container[offset]
    original_length, offset = decode_uvarint(container, offset + 1)
    if stream_mode == STREAM_RAW:
        payload = container[offset:]
        if len(payload) != original_length:
            raise ValueError("raw stream length mismatch")
        return payload
    if stream_mode != STREAM_BLOCKS:
        raise ValueError("unknown stream mode")
    block_size, offset = decode_uvarint(container, offset)
    block_count, offset = decode_uvarint(container, offset)
    if block_size <= 0:
        raise ValueError("invalid block size")
    expected_count = (
        (original_length + block_size - 1) // block_size if original_length else 0
    )
    if block_count != expected_count:
        raise ValueError("block count does not match stream length")

    output = bytearray()
    for index in range(block_count):
        if offset >= len(container):
            raise ValueError("truncated block mode")
        try:
            mode = Mode(container[offset])
        except ValueError as error:
            raise ValueError("unknown block mode") from error
        block_length, offset = decode_uvarint(container, offset + 1)
        payload_length, offset = decode_uvarint(container, offset)
        expected_length = min(block_size, original_length - index * block_size)
        if block_length != expected_length:
            raise ValueError("invalid declared block length")
        end = offset + payload_length
        payload = container[offset:end]
        if len(payload) != payload_length:
            raise ValueError("truncated block payload")
        output += decode_payload(mode, payload, block_length)
        offset = end

    if offset != len(container):
        raise ValueError("trailing stream bytes")
    if len(output) != original_length:
        raise ValueError("decoded stream length mismatch")
    return bytes(output)
