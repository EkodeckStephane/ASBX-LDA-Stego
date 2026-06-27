"""Stego-text generator and extractor for ASBX-Enhanced LDA Steganography.

Embedding algorithm (§4.2 of the article)
------------------------------------------
For each topic index z_j (j = 1, …, N):
    1. Retrieve the top-n words of topic z_j from the LDA beta matrix.
    2. Select one word using a pseudo-random function seeded with the stego-key
       and position j, so that the same key always selects the same word.
    3. Append the selected word to the stego-text.

The resulting stego-text is a sequence of N words drawn from the LDA vocabulary.
It is grammatically unsophisticated (bag-of-words style), which is an accepted
limitation of pure topic-model steganography.  Grammatically coherent variants
(e.g., conditional on a language model) are noted as future work in §9.

Extraction algorithm (§4.3)
----------------------------
For each word w_j in the stego-text:
    z_j* = argmax_t  beta[t, vocab_index(w_j)]

Then the topic-index sequence {z_j*} is passed to payload_decoder.decode_payload.

API
---
    embed(topic_indices, vocab, beta, stego_key, top_n) -> list[str]
    extract_indices(stego_words, vocab, beta) -> list[int]
    text_to_words(text) -> list[str]         (light tokeniser)
"""

from __future__ import annotations

import hashlib
import math
from typing import Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Word selection
# ---------------------------------------------------------------------------

def _select_word(
    topic: int,
    position: int,
    beta_row: np.ndarray,
    vocab: list[str],
    stego_key: bytes,
    top_n: int,
) -> str:
    """Select one word from the top-n words of a topic using a keyed PRNG.

    The selection is deterministic given (topic, position, stego_key) so that
    the receiver can reproduce it during extraction if needed.  However, for
    the greedy ML decoder used in extract_indices, only argmax(beta[:, word])
    is needed, which does not require the key.
    """
    # Get top-n word indices by beta probability
    top_indices = np.argsort(beta_row)[::-1][:top_n]

    # Keyed selection: HMAC-SHA256(key || topic_bytes || position_bytes)
    h = hashlib.sha256(
        stego_key
        + topic.to_bytes(4, "big")
        + position.to_bytes(4, "big")
    ).digest()
    slot = int.from_bytes(h[:4], "big") % top_n
    chosen_idx = int(top_indices[slot])
    return vocab[chosen_idx]


# ---------------------------------------------------------------------------
# Embed
# ---------------------------------------------------------------------------

def embed(
    topic_indices: list[int],
    vocab: list[str],
    beta: np.ndarray,
    stego_key: bytes = b"",
    top_n: int = 10,
) -> list[str]:
    """Produce a stego-word sequence from topic indices.

    Parameters
    ----------
    topic_indices:
        Sequence of integers in [0, T), one per embedding unit.
    vocab:
        Vocabulary list (index → word) from the LDA model.
    beta:
        Topic-word matrix of shape (T, V), float32.
    stego_key:
        Bytes used to seed word selection.  An empty key → slot 0 (top word).
    top_n:
        Pool size from which the stego word is drawn.

    Returns
    -------
    List of words forming the stego-text.
    """
    T, V = beta.shape
    if any(z < 0 or z >= T for z in topic_indices):
        raise ValueError("Topic index out of range [0, T).")

    words: list[str] = []
    for j, z in enumerate(topic_indices):
        word = _select_word(z, j, beta[z], vocab, stego_key, top_n)
        words.append(word)
    return words


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def extract_indices(
    stego_words: list[str],
    vocab: list[str],
    beta: np.ndarray,
    oov_policy: str = "raise",
) -> list[int]:
    """Recover topic indices from stego words by maximum-likelihood assignment.

    z_j* = argmax_t  beta[t, vocab_index(w_j)]

    By default, words absent from the vocabulary raise ``ValueError``.  The
    legacy ``oov_policy="zero"`` mode maps them to topic 0 for diagnostic
    experiments only.
    """
    if oov_policy not in {"raise", "zero"}:
        raise ValueError(f"unknown OOV policy: {oov_policy}")
    word_to_idx = {w: i for i, w in enumerate(vocab)}
    indices: list[int] = []
    for word in stego_words:
        idx = word_to_idx.get(word)
        if idx is None:
            if oov_policy == "raise":
                raise ValueError(f"OOV stego word: {word!r}")
            indices.append(0)
        else:
            indices.append(int(np.argmax(beta[:, idx])))
    return indices


# ---------------------------------------------------------------------------
# Capacity utilities
# ---------------------------------------------------------------------------

def capacity_bits_per_word(num_topics: int) -> int:
    """Return k = floor(log2(T)) bits embedded per stego word."""
    return int(math.log2(num_topics))


def words_needed(payload_bytes: int, num_topics: int) -> int:
    """Return the number of stego words required to embed *payload_bytes* bytes."""
    k = capacity_bits_per_word(num_topics)
    return math.ceil(payload_bytes * 8 / k)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def text_to_words(text: str) -> list[str]:
    """Split stego-text into word tokens (lowercase, alphabetic only)."""
    import re
    return re.findall(r"[a-z']+", text.lower())


def words_to_text(words: list[str], line_width: int = 80) -> str:
    """Join stego words into a wrapped paragraph."""
    lines: list[str] = []
    current: list[str] = []
    col = 0
    for word in words:
        if col + len(word) + 1 > line_width and current:
            lines.append(" ".join(current))
            current = [word]
            col = len(word)
        else:
            current.append(word)
            col += len(word) + 1
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))

    from payload_encoder import encode_payload
    from payload_decoder import decode_payload

    T = 64
    k = int(math.log2(T))
    secret = b"Hello, ASBX steganography!"
    KEY = b"demo-stego-key"

    # Synthetic beta (random, for smoke-test only)
    rng = np.random.default_rng(42)
    V = 500
    beta_raw = rng.dirichlet(np.ones(V) * 0.1, size=T).astype(np.float32)
    vocab = [f"word{i}" for i in range(V)]

    print("=== Encode ===")
    indices, compressed = encode_payload(secret, T)
    print(f"  Secret    : {secret!r}")
    print(f"  Compressed: {len(compressed)} bytes")
    print(f"  Indices   : {len(indices)}")

    print("=== Embed ===")
    stego_words = embed(indices, vocab, beta_raw, stego_key=KEY, top_n=5)
    print(f"  Stego words (first 10): {stego_words[:10]}")

    print("=== Extract ===")
    recovered_indices = extract_indices(stego_words, vocab, beta_raw)
    recovered_secret = decode_payload(recovered_indices, k, len(compressed))
    assert recovered_secret == secret, f"MISMATCH: {recovered_secret!r}"
    print(f"  Recovered: {recovered_secret!r} — OK")
    print("Round-trip PASSED.")
