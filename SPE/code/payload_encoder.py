"""Payload encoder for ASBX-Enhanced LDA Text Steganography.

Pipeline
--------
    secret bytes  →  [ASBX compress]  →  compressed bytes
                  →  [bit chunking, k bits per chunk]  →  topic index sequence
                  →  [serialised as length-prefixed uint16 list]  →  embedding units

The number of topic indices to embed equals the number of words that the
stego-generator will produce.  The receiver only needs the topic index
sequence to recover the compressed payload; the original length is carried
inside the ASBX container, enabling exact decoding.

API
---
    encode_payload(secret: bytes, num_topics: int, block_size: int = 256)
        -> (topic_indices: list[int], compressed_bytes: bytes)

    topic_indices_to_bits(indices: list[int], k: int) -> bytes
        (helper used by the decoder to reconstruct compressed bytes)

Notation (matches the article §4)
----------------------------------
    T  = num_topics   (must be a power of 2)
    k  = log2(T)      (bits per chunk)
    b  = binary representation of compressed payload
    z_j= j-th topic index = b[j*k : (j+1)*k] interpreted as big-endian integer
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the ASBX package
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]  # SPE/../.. = ASBX repo root
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))

from asbc import decode, encode, encode_deterministic  # noqa: E402  (after sys.path manipulation)


# ---------------------------------------------------------------------------
# Core encode
# ---------------------------------------------------------------------------

def encode_payload(
    secret: bytes,
    num_topics: int,
    block_size: int = 256,
    selector: str = "deterministic",
) -> tuple[list[int], bytes]:
    """Compress *secret* with ASBX then map to a topic-index sequence.

    Parameters
    ----------
    secret:
        Raw bytes to hide.
    num_topics:
        Number of LDA topics T; must be a power of 2 ≥ 2.
    block_size:
        ASBX block granularity in bytes (default 256).
    selector:
        ``"deterministic"`` uses the practical non-oracle ASBX selector.
        ``"oracle"`` uses the exact minimum serialized block record and is
        intended only for upper-bound experiments.

    Returns
    -------
    topic_indices:
        Sequence of integers in [0, T), one per k-bit chunk of the
        compressed payload (padded to a multiple of k with trailing zeros).
    compressed:
        The ASBX container (needed only for size-measurement; the decoder
        reconstructs it from topic_indices via bits_to_bytes).
    """
    if num_topics < 2 or (num_topics & (num_topics - 1)) != 0:
        raise ValueError(f"num_topics must be a power of 2, got {num_topics}")

    k = int(math.log2(num_topics))
    if selector == "deterministic":
        compressed = encode_deterministic(secret, block_size=block_size)
    elif selector == "oracle":
        compressed = encode(secret, block_size=block_size)
    else:
        raise ValueError(f"unknown ASBX selector: {selector}")
    indices = _bytes_to_topic_indices(compressed, k, num_topics)
    return indices, compressed


def _bytes_to_topic_indices(data: bytes, k: int, num_topics: int) -> list[int]:
    """Convert *data* to a sequence of k-bit topic indices.

    The bit string is padded on the right with zeros to a multiple of k.
    """
    # Build bit string
    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)

    # Pad to multiple of k
    remainder = len(bits) % k
    if remainder:
        bits.extend([0] * (k - remainder))

    # Group into k-bit chunks → topic indices
    indices: list[int] = []
    for start in range(0, len(bits), k):
        chunk = bits[start : start + k]
        idx = sum(b << (k - 1 - i) for i, b in enumerate(chunk))
        assert 0 <= idx < num_topics
        indices.append(idx)

    return indices


# ---------------------------------------------------------------------------
# Inverse helpers (used by the decoder to reconstruct compressed bytes)
# ---------------------------------------------------------------------------

def topic_indices_to_bytes(indices: list[int], k: int, original_byte_length: int) -> bytes:
    """Reconstruct a byte sequence from topic indices.

    Parameters
    ----------
    indices:
        Sequence of integers in [0, 2^k).
    k:
        Bits per index.
    original_byte_length:
        Exact byte count of the compressed container (known to the decoder
        because ASBX embeds the original length; however, the *compressed*
        length must be communicated separately — see payload_decoder.py).

    Returns
    -------
    Reconstructed bytes of length *original_byte_length*.
    """
    bits: list[int] = []
    for idx in indices:
        for shift in range(k - 1, -1, -1):
            bits.append((idx >> shift) & 1)

    # Trim to exact byte boundary
    total_bits = original_byte_length * 8
    bits = bits[:total_bits]

    result = bytearray()
    for i in range(0, len(bits), 8):
        byte_bits = bits[i : i + 8]
        byte_val = sum(b << (7 - j) for j, b in enumerate(byte_bits))
        result.append(byte_val)

    return bytes(result)


# ---------------------------------------------------------------------------
# Capacity metrics
# ---------------------------------------------------------------------------

def embedding_stats(
    secret: bytes,
    compressed: bytes,
    num_topics: int,
    num_cover_words: int,
) -> dict:
    """Return embedding capacity statistics for one payload.

    Parameters
    ----------
    secret:
        Original plaintext payload.
    compressed:
        ASBX-compressed payload.
    num_topics:
        T (power of 2).
    num_cover_words:
        Number of words in the cover text used to embed the payload.

    Returns
    -------
    dict with keys:
        secret_bytes, compressed_bytes, asbx_ratio,
        k_bits_per_word, topic_indices_needed,
        cover_capacity_bits, utilisation, capacity_gain_factor.
    """
    k = int(math.log2(num_topics))
    compressed_bits = len(compressed) * 8
    indices_needed = math.ceil(compressed_bits / k)
    cover_capacity_bits = num_cover_words * k
    utilisation = indices_needed / num_cover_words if num_cover_words > 0 else float("inf")

    # Without ASBX: raw secret bits
    raw_indices_needed = math.ceil(len(secret) * 8 / k)

    return {
        "secret_bytes": len(secret),
        "compressed_bytes": len(compressed),
        "asbx_ratio": len(compressed) / len(secret) if secret else 1.0,
        "k_bits_per_word": k,
        "topic_indices_needed": indices_needed,
        "raw_indices_needed": raw_indices_needed,
        "cover_capacity_bits_at_N_words": cover_capacity_bits,
        "utilisation_fraction": utilisation,
        "capacity_gain_factor": raw_indices_needed / indices_needed if indices_needed > 0 else 1.0,
    }


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="ASBX payload encoder smoke-test.")
    p.add_argument("--secret", default="Hello, steganography!", help="Secret message string.")
    p.add_argument("--topics", type=int, default=64, help="Number of LDA topics.")
    p.add_argument("--block-size", type=int, default=256)
    args = p.parse_args()

    secret_bytes = args.secret.encode()
    indices, compressed = encode_payload(secret_bytes, args.topics, args.block_size)

    k = int(math.log2(args.topics))
    print(f"Secret          : {len(secret_bytes)} bytes")
    print(f"Compressed      : {len(compressed)} bytes  (ratio {len(compressed)/len(secret_bytes):.4f})")
    print(f"Topic indices   : {len(indices)}  (k={k} bits each)")

    # Verify round-trip
    reconstructed_compressed = topic_indices_to_bytes(indices, k, len(compressed))
    assert reconstructed_compressed == compressed, "Round-trip FAILED"
    reconstructed_secret = decode(reconstructed_compressed)
    assert reconstructed_secret == secret_bytes, "ASBX decode FAILED"
    print("Round-trip      : OK")
