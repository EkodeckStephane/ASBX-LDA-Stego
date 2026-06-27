"""LDA corpus trainer for ASBX-Enhanced Steganography.

Trains a Latent Dirichlet Allocation model on a given text corpus and
persists the vocabulary and per-topic word distributions needed by the
stego-generator.

Usage
-----
    python lda_trainer.py --corpus path/to/corpus.txt \
                          --topics 64 \
                          --output models/lda_T64

Output files
------------
    <output>.vocab   : JSON, list[str] of vocabulary (index → word)
    <output>.beta    : NPY, float32 array (T, V) of topic-word distributions
    <output>.meta    : JSON, training metadata
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Optional dependency: gensim (preferred) or sklearn fallback
# ---------------------------------------------------------------------------

try:
    from gensim import corpora
    from gensim.models import LdaModel

    _BACKEND = "gensim"
except ImportError:  # pragma: no cover
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    _BACKEND = "sklearn"


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z']+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def load_documents(corpus_path: Path, max_docs: int | None) -> list[list[str]]:
    docs: list[list[str]] = []
    with corpus_path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            tokens = tokenize(line)
            if len(tokens) >= 5:
                docs.append(tokens)
            if max_docs and len(docs) >= max_docs:
                break
    return docs


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_gensim(
    docs: list[list[str]],
    num_topics: int,
    passes: int,
    random_state: int,
) -> tuple[list[str], np.ndarray]:
    dictionary = corpora.Dictionary(docs)
    dictionary.filter_extremes(no_below=5, no_above=0.5)
    corpus_bow = [dictionary.doc2bow(doc) for doc in docs]

    model = LdaModel(
        corpus=corpus_bow,
        id2word=dictionary,
        num_topics=num_topics,
        passes=passes,
        random_state=random_state,
        alpha="auto",
        eta="auto",
    )

    vocab = [dictionary[i] for i in range(len(dictionary))]
    # beta[t, v] = P(word v | topic t)
    beta = model.get_topics().astype(np.float32)  # shape (T, V)
    return vocab, beta


def train_sklearn(
    docs: list[list[str]],
    num_topics: int,
    passes: int,
    random_state: int,
) -> tuple[list[str], np.ndarray]:
    texts = [" ".join(d) for d in docs]
    vectorizer = CountVectorizer(min_df=5, max_df=0.5)
    X = vectorizer.fit_transform(texts)

    lda = LatentDirichletAllocation(
        n_components=num_topics,
        max_iter=passes,
        random_state=random_state,
    )
    lda.fit(X)

    vocab = vectorizer.get_feature_names_out().tolist()
    # Normalise rows to get proper distributions
    beta_raw = lda.components_
    beta = (beta_raw / beta_raw.sum(axis=1, keepdims=True)).astype(np.float32)
    return vocab, beta


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_model(output_prefix: Path, vocab: list[str], beta: np.ndarray, meta: dict) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    vocab_path = output_prefix.with_suffix(".vocab")
    beta_path = output_prefix.with_suffix(".beta.npy")
    meta_path = output_prefix.with_suffix(".meta")

    with vocab_path.open("w", encoding="utf-8") as fh:
        json.dump(vocab, fh, ensure_ascii=False)

    np.save(beta_path, beta)

    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"  vocab  → {vocab_path}  ({len(vocab)} words)")
    print(f"  beta   → {beta_path}  shape={beta.shape}")
    print(f"  meta   → {meta_path}")


def load_model(output_prefix: Path) -> tuple[list[str], np.ndarray]:
    """Reload a saved model; used by stego_generator and capacity_benchmark."""
    vocab_path = output_prefix.with_suffix(".vocab")
    beta_path = output_prefix.with_suffix(".beta.npy")
    with vocab_path.open(encoding="utf-8") as fh:
        vocab = json.load(fh)
    beta = np.load(str(beta_path))
    return vocab, beta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train an LDA model for ASBX steganography.")
    p.add_argument("--corpus", required=True, type=Path, help="Path to text corpus (one sentence/paragraph per line).")
    p.add_argument("--topics", type=int, default=64, help="Number of LDA topics T (default: 64; must be a power of 2 for k=log2(T) exact bit mapping).")
    p.add_argument("--passes", type=int, default=20, help="Training passes/iterations.")
    p.add_argument("--max-docs", type=int, default=None, help="Limit corpus to this many lines.")
    p.add_argument("--seed", type=int, default=42, help="Random seed.")
    p.add_argument("--output", type=Path, required=True, help="Output prefix, e.g. models/lda_T64.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.topics < 2 or (args.topics & (args.topics - 1)) != 0:
        print(f"ERROR: --topics must be a power of 2 (got {args.topics}).", file=sys.stderr)
        sys.exit(1)

    print(f"Backend : {_BACKEND}")
    print(f"Corpus  : {args.corpus}")
    print(f"Topics  : {args.topics}  (k = {args.topics.bit_length() - 1} bits per chunk)")

    t0 = time.perf_counter()
    docs = load_documents(args.corpus, args.max_docs)
    print(f"Loaded  : {len(docs)} documents in {time.perf_counter() - t0:.1f}s")

    t1 = time.perf_counter()
    if _BACKEND == "gensim":
        vocab, beta = train_gensim(docs, args.topics, args.passes, args.seed)
    else:
        vocab, beta = train_sklearn(docs, args.topics, args.passes, args.seed)
    elapsed = time.perf_counter() - t1
    print(f"Trained : {elapsed:.1f}s  |  beta shape = {beta.shape}")

    meta = {
        "backend": _BACKEND,
        "num_topics": args.topics,
        "k_bits": args.topics.bit_length() - 1,
        "vocab_size": len(vocab),
        "passes": args.passes,
        "seed": args.seed,
        "corpus": str(args.corpus),
        "num_docs": len(docs),
        "train_seconds": round(elapsed, 2),
    }

    save_model(args.output, vocab, beta, meta)
    print("Done.")


if __name__ == "__main__":
    main()
