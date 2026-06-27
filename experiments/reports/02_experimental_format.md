# ASBX Experimental Format, Version 0

This format exists to validate modes and exact accounting. It is deliberately
not called version `1.0`.

All integers are unsigned LEB128.

## Stream

| Field | Encoding |
|---|---|
| Magic | ASCII `ASBX` |
| Version | one byte, value `0` |
| Stream mode | one byte: raw (`0`) or adaptive blocks (`1`) |
| Original byte length | uvarint |

Raw stream mode then stores exactly the original bytes. Adaptive mode
continues with:

| Field | Encoding |
|---|---|
| Nominal block size | uvarint |
| Block count | uvarint |
| Block records | repeated exactly `block count` times |

## Block record

| Field | Encoding |
|---|---|
| Mode | one byte |
| Original block length | uvarint |
| Payload length | uvarint |
| Payload | declared number of bytes |

Modes are raw (`0`), zero (`1`), boundary trim (`2`), set-bit gaps (`3`),
zero-bit gaps (`4`), set-bit runs (`5`), and nonzero-byte positions with
values (`6`).

The encoder compares the complete adaptive stream with the complete raw stream
and emits the shorter candidate.

The trim payload stores leading-zero count, trailing-zero count, and the
remaining bytes. A positional payload stores the number of selected positions
followed by positive gap values. Bit positions are zero-based in MSB-first
order. The first gap is `position + 1`; later gaps are position differences.

The set-bit-run payload stores the run count followed by pairs containing the
zero gap from the preceding run end and the positive run length. The
nonzero-byte payload stores the number of nonzero bytes followed by positive
position gaps and literal nonzero byte values.

The decoder rejects unknown modes, non-canonical or truncated uvarints,
impossible lengths, invalid gaps, duplicate/out-of-range positions, nonzero
padding conditions, trailing bytes, and decoded-length disagreement.
