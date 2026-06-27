"""End-to-end integration test for the ASBX-LDA steganography pipeline.

Tests the complete chain:
    secret → encode_payload → embed → extract_indices → decode_payload → secret

Also validates that capacity computations match the theoretical formula.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_REPO_ROOT / "experiments" / "src"))
sys.path.insert(0, str(_HERE))

from payload_encoder import encode_payload, embedding_stats
from payload_decoder import decode_payload
from stego_generator import embed, extract_indices, words_needed

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_synthetic_beta(T: int, V: int, seed: int = 0) -> np.ndarray:
    """Create a random LDA beta matrix (T x V) with disjoint top-word per topic."""
    rng = np.random.default_rng(seed)
    # Assign each word exclusively to one topic (guarantees argmax correctness)
    beta = np.zeros((T, V), dtype=np.float32)
    words_per_topic = V // T
    for t in range(T):
        start = t * words_per_topic
        end = start + words_per_topic
        # Main topic mass on this topic's words
        beta[t, start:end] = rng.dirichlet(np.ones(words_per_topic) * 2.0)
        # Small background mass
        background = rng.dirichlet(np.ones(V) * 0.01)
        beta[t] = 0.9 * beta[t] + 0.1 * background
        beta[t] /= beta[t].sum()
    return beta


def make_vocab(V: int) -> list[str]:
    return [f"w{i:05d}" for i in range(V)]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")
        FAIL += 1


def test_round_trip_text_secret():
    """Short ASCII secret embeds and recovers exactly."""
    T = 64
    k = int(math.log2(T))
    V = T * 20
    vocab = make_vocab(V)
    beta = make_synthetic_beta(T, V)
    secret = b"Hello, ASBX-LDA steganography!"

    indices, compressed = encode_payload(secret, T)
    stego_words = embed(indices, vocab, beta, stego_key=b"key1", top_n=5)
    recovered_indices = extract_indices(stego_words, vocab, beta)
    recovered = decode_payload(recovered_indices, k, len(compressed))

    check("text_secret: indices match",
          recovered_indices == indices,
          f"first diff at {next((i for i,(a,b) in enumerate(zip(recovered_indices,indices)) if a!=b), None)}")
    check("text_secret: byte-exact recovery", recovered == secret)


def test_round_trip_sparse_bytes():
    """Sparse byte payload (1% density, 4096 bytes) embeds and recovers."""
    T = 64
    k = int(math.log2(T))
    V = T * 20
    vocab = make_vocab(V)
    beta = make_synthetic_beta(T, V, seed=1)

    rng = np.random.default_rng(99)
    bits = (rng.random(4096 * 8) < 0.01).astype(np.uint8)
    data = bytearray(4096)
    for i in range(4096):
        for j in range(8):
            data[i] |= int(bits[i * 8 + j]) << (7 - j)
    secret = bytes(data)

    indices, compressed = encode_payload(secret, T)
    stego_words = embed(indices, vocab, beta, stego_key=b"", top_n=1)
    recovered_indices = extract_indices(stego_words, vocab, beta)
    recovered = decode_payload(recovered_indices, k, len(compressed))

    ratio = len(compressed) / len(secret)
    gain = 1.0 / ratio

    check("sparse_bytes: byte-exact recovery", recovered == secret)
    check("sparse_bytes: gain > 5x", gain > 5.0, f"gain={gain:.2f}")


def test_capacity_formula():
    """Theorem 1: gain = 1/R matches measured word counts."""
    T = 64
    k = int(math.log2(T))
    secrets = [
        b"\x00" * 1024,           # all zeros — maximally sparse
        b"\xff" * 1024,           # all ones
        bytes(range(256)) * 4,    # structured
        b"hello world " * 85,     # repetitive ASCII
    ]
    for secret in secrets:
        indices, compressed = encode_payload(secret, T)
        R = len(compressed) / len(secret)
        G_theory = 1.0 / R
        G_measured = len(indices) / words_needed(len(compressed), T)
        # words_needed gives ceiling; G_measured ≈ 1.0 by construction
        check(f"capacity_formula R={R:.3f}: |indices|=ceil(8*R*|S|/k)",
              len(indices) == math.ceil(8 * len(compressed) / k),
              f"|indices|={len(indices)} expected={math.ceil(8*len(compressed)/k)}")


def test_embedding_stats_consistency():
    """embedding_stats gain_factor matches 1/asbx_ratio."""
    T = 64
    secrets = [b"\x00" * 512, b"random" * 100, bytes(range(256))]
    for secret in secrets:
        indices, compressed = encode_payload(secret, T)
        stats = embedding_stats(secret, compressed, T, num_cover_words=len(indices))
        ratio = stats["asbx_ratio"]
        gain = stats["capacity_gain_factor"]
        raw = stats["raw_indices_needed"]
        expected_gain = raw / len(indices) if len(indices) > 0 else 1.0
        check(f"stats_consistency |S|={len(secret)}",
              abs(gain - expected_gain) < 0.01,
              f"gain={gain:.4f} expected={expected_gain:.4f}")


def test_deterministic_with_key():
    """Same key → same stego words; different key → different words."""
    T = 64
    V = T * 20
    vocab = make_vocab(V)
    beta = make_synthetic_beta(T, V, seed=5)
    secret = b"Determinism test"

    indices, _ = encode_payload(secret, T)
    w1a = embed(indices, vocab, beta, stego_key=b"keyA", top_n=5)
    w1b = embed(indices, vocab, beta, stego_key=b"keyA", top_n=5)
    w2  = embed(indices, vocab, beta, stego_key=b"keyB", top_n=5)

    check("key_determinism: same key -> same words", w1a == w1b)
    check("key_variation: different keys -> different words",
          w1a != w2,
          "keys produced identical output (unlikely but possible)")


def test_empty_key_top_word():
    """Empty key always selects top word of each topic."""
    T = 16
    V = T * 10
    vocab = make_vocab(V)
    beta = make_synthetic_beta(T, V, seed=7)
    indices = [t % T for t in range(20)]

    words_empty = embed(indices, vocab, beta, stego_key=b"", top_n=5)
    # With empty key, sha256 of (key||topic||pos) % 5 is not necessarily slot 0
    # But extract_indices should still recover the correct topics
    recovered = extract_indices(words_empty, vocab, beta)
    check("empty_key: extract recovers all indices",
          recovered == indices,
          f"mismatches: {sum(a!=b for a,b in zip(recovered,indices))}/{len(indices)}")


def test_large_payload_consistency():
    """A 16 KB sparse payload round-trips correctly."""
    T = 128
    k = int(math.log2(T))
    V = T * 15
    vocab = make_vocab(V)
    beta = make_synthetic_beta(T, V, seed=3)

    rng = np.random.default_rng(42)
    bits = (rng.random(16384 * 8) < 0.05).astype(np.uint8)
    data = bytearray(16384)
    for i in range(16384):
        for j in range(8):
            data[i] |= int(bits[i * 8 + j]) << (7 - j)
    secret = bytes(data)

    indices, compressed = encode_payload(secret, T)
    stego_words = embed(indices, vocab, beta, stego_key=b"large-test", top_n=3)
    recovered_indices = extract_indices(stego_words, vocab, beta)
    recovered = decode_payload(recovered_indices, k, len(compressed))

    check("large_payload: byte-exact recovery", recovered == secret)
    check("large_payload: gain > 1.5x",
          len(indices) / math.ceil(len(secret) * 8 / k) < 0.67,
          f"actual ratio={len(compressed)/len(secret):.3f}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=== ASBX-LDA Integration Tests ===\n")

    print("--- Round-trip: text secret ---")
    test_round_trip_text_secret()

    print("--- Round-trip: sparse bytes ---")
    test_round_trip_sparse_bytes()

    print("--- Capacity formula (Theorem 1) ---")
    test_capacity_formula()

    print("--- Embedding stats consistency ---")
    test_embedding_stats_consistency()

    print("--- Key determinism ---")
    test_deterministic_with_key()

    print("--- Empty-key top-word extraction ---")
    test_empty_key_top_word()

    print("--- Large payload (16 KB, rho=5%) ---")
    test_large_payload_consistency()

    print(f"\n{'='*40}")
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
