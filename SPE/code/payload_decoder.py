"""Payload decoder for ASBX-Enhanced LDA Text Steganography.

Inverse pipeline
----------------
    stego-text  →  [LDA inference]  →  topic index sequence
               →  [k-bit reconstruction]  →  compressed bytes (ASBX container)
               →  [ASBX decode]  →  original secret bytes

The decoder needs two side-channel values transmitted alongside the
stego-text (e.g., as part of the stego-key or an authenticated header):
    - compressed_length  : exact byte length of the ASBX container
    - num_topics (T)     : the LDA configuration used during embedding

These values are small (< 16 bytes total) and may be transmitted over an
authenticated out-of-band channel or embedded as a fixed-length prefix in
the first few topic-index words.

API
---
    decode_payload(topic_indices, k, compressed_length) -> bytes
        Reconstruct the secret from topic indices, bits-per-chunk, and the
        exact compressed container length.

    infer_topic_indices(stego_words, vocab, beta, k) -> list[int]
        Given a list of stego words and the LDA beta matrix, recover the
        most likely topic index that generated each word.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Locate the ASBX package
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))

from asbc import decode as asbx_decode  # noqa: E402
from payload_encoder import topic_indices_to_bytes  # noqa: E402


# ---------------------------------------------------------------------------
# Core decode
# ---------------------------------------------------------------------------

def decode_payload(
    topic_indices: list[int],
    k: int,
    compressed_length: int,
) -> bytes:
    """Recover the secret bytes from a topic-index sequence.

    Parameters
    ----------
    topic_indices:
        Sequence of integers in [0, 2^k), as recovered by LDA inference.
    k:
        Bits per topic index (= log2(T)).
    compressed_length:
        Exact byte length of the ASBX container embedded during encoding.
        This value must be transmitted to the receiver as part of the stego-key.

    Returns
    -------
    Original secret bytes (exactly as passed to encode_payload).
    """
    compressed = topic_indices_to_bytes(topic_indices, k, compressed_length)
    return asbx_decode(compressed)


# ---------------------------------------------------------------------------
# LDA inference
# ---------------------------------------------------------------------------

def infer_topic_indices(
    stego_words: list[str],
    vocab: list[str],
    beta: np.ndarray,
    k: int,
) -> list[int]:
    """Recover the topic index that most likely generated each stego word.

    This is a greedy maximum-likelihood assignment:
        z_j* = argmax_t P(word_j | topic t) = argmax_t beta[t, word_j_idx]

    This corresponds to the decoding rule described in §4.3 of the article.

    Parameters
    ----------
    stego_words:
        Ordered list of words extracted from the stego-text.
    vocab:
        Vocabulary list (index → word), as returned by lda_trainer.load_model.
    beta:
        Topic-word distribution matrix of shape (T, V), float32.
    k:
        Expected bits per topic index; used only for validation.

    Returns
    -------
    List of integers in [0, T), one per stego word.
    Notes
    -----
    Words not found in the vocabulary are assigned topic 0 (neutral fallback).
    For a production system, an out-of-vocabulary sentinel should be inserted
    during embedding to flag such positions explicitly.
    """
    word_to_idx = {w: i for i, w in enumerate(vocab)}
    T = beta.shape[0]
    indices: list[int] = []

    for word in stego_words:
        idx = word_to_idx.get(word)
        if idx is None:
            indices.append(0)
        else:
            topic = int(np.argmax(beta[:, idx]))
            indices.append(topic)

    assert all(0 <= z < T for z in indices), "Recovered topic index out of range"
    return indices


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def decode_stego_text(
    stego_words: list[str],
    vocab: list[str],
    beta: np.ndarray,
    k: int,
    compressed_length: int,
) -> bytes:
    """End-to-end decode: stego words → secret bytes.

    Parameters
    ----------
    stego_words:
        Words recovered from the stego-text (in order).
    vocab, beta:
        LDA model as loaded by lda_trainer.load_model.
    k:
        Bits per topic index (log2 T).
    compressed_length:
        Byte length of the ASBX container (side-channel value).

    Returns
    -------
    Recovered secret bytes.
    """
    topic_indices = infer_topic_indices(stego_words, vocab, beta, k)
    return decode_payload(topic_indices, k, compressed_length)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import math
    from payload_encoder import encode_payload

    # Minimal self-test without a real LDA model
    secret = b"Test payload for round-trip verification."
    T = 64
    k = int(math.log2(T))
    block_size = 256

    print("=== Encoder ===")
    indices, compressed = encode_payload(secret, T, block_size)
    print(f"  Secret     : {len(secret)} bytes")
    print(f"  Compressed : {len(compressed)} bytes")
    print(f"  Indices    : {len(indices)}")

    print("=== Decoder ===")
    recovered = decode_payload(indices, k, len(compressed))
    assert recovered == secret, f"Mismatch: {recovered!r} != {secret!r}"
    print(f"  Recovered  : {len(recovered)} bytes — OK")
    print("Round-trip PASSED.")
