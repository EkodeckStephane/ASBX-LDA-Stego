# ASBX-LDA-Stego

ASBX-LDA-Stego is a reproducible research artefact for adaptive sparse block
coding and its use in implementation-oriented text steganography experiments.
The repository contains the Python reference codec, a native C implementation,
tests, dataset generators, benchmark scripts, and machine-readable experiment
outputs. The manuscript itself is intentionally not stored in this public code
repository.

The current `ASBX` container is experimental format version `0`. It is stable
enough for reproducible evaluation, but it is not yet a frozen `1.0` file
format.

## Context

Sparse byte and bit structures occur in practical software artefacts: encoded
features, sparse matrices, mask-like tensors, padded records, and intermediate
payloads used by steganographic or data-hiding pipelines. These data often mix
zero-heavy blocks, short dense regions, long bit gaps, and incompressible
controls. A single hand-picked representation tends to work well only for one
of these cases.

## Problem

The implementation problem is to represent sparse heterogeneous payloads in a
lossless, decodable, and reproducible way while keeping the software simple
enough to audit. Measurements must report complete serialized containers, not
payload-only estimates, and the codec must survive round-trip and malformed
stream tests.

## Research Question

Can a deterministic block-adaptive container select among simple sparse
representations and provide practical compression behaviour across software
payload families while remaining implementable in both a Python reference and a
portable native C artefact?

## Problematic

The core tension is between compression adaptivity and engineering credibility.
Oracle-only selection can overstate performance; payload-only accounting can
hide metadata cost; Python-only prototypes can be too slow to support a
practice-oriented software engineering claim. ASBX addresses these issues by
using complete container sizes, deterministic non-oracle selection, cross-codec
compatibility tests, and native benchmarks.

## Proposed Solution

ASBX encodes input as fixed-size blocks and chooses one record mode per block.
The implemented modes are:

- raw block;
- all-zero block;
- reversible leading/trailing zero trimming;
- positions of set bits encoded as gaps;
- positions of zero bits encoded as gaps;
- runs of one bits;
- non-zero byte positions and values.

The encoder emits a complete `ASBX` container with magic bytes, format version,
stream mode, original length, block metadata, and payload records. It also keeps
a global raw fallback, so encoded output is never forced to be larger than the
raw container when block coding is not beneficial.

## Means Used

The artefact combines:

- Python reference implementation in `experiments/src/asbc`;
- native C implementation and CLI in `experiments/native/asbx_c`;
- deterministic synthetic corpus generators;
- optional larger generated corpus for throughput checks;
- external-corpus preparation scripts for sparse matrices and image tensors;
- Pytest compatibility, round-trip, selector, mode, and malformed-stream tests;
- native C build scripts for MSYS2 UCRT64, GCC, and Clang-oriented checks.

## Results

The current reproducibility suite validates the complete ASBX container format
and Python/C interoperability. The native C benchmark strengthens the practical
software claim: on the local SPE artefact benchmark, C encoding reaches roughly
`60-112 MiB/s` depending on domain, with median encode speedups of about
`66x-154x` over the deterministic Python reference. These numbers are local
benchmark outputs, not universal hardware-independent claims.

## Positioning

This repository is positioned as an implementation artefact for practical
software engineering research. It is not a general-purpose replacement for
mature compressors such as DEFLATE, Zstandard, or LZMA. Its role is narrower:
to study how a transparent, block-adaptive sparse representation behaves in
software and steganography-related payload pipelines, with reproducible source
code and auditable measurements.

## Quick Start

Run the Python test suite:

```powershell
python -m pytest experiments\tests -q
```

Build the native C CLI on Windows with MSYS2 UCRT64:

```powershell
powershell -ExecutionPolicy Bypass -File experiments\native\asbx_c\build.ps1
```

Run a native round-trip:

```powershell
experiments\native\asbx_c\asbxc.exe encode --block-size 256 input.bin output.asbx
experiments\native\asbx_c\asbxc.exe validate output.asbx
experiments\native\asbx_c\asbxc.exe decode output.asbx recovered.bin
```

Run the code-level reproducibility workflow:

```powershell
.\experiments\run_reproducibility.ps1
```

Generate and benchmark larger deterministic payloads:

```powershell
python experiments\scripts\generate_large_corpus.py
python experiments\scripts\run_large_native_benchmark.py
```

## Scientific Rule

All reported compression sizes must be the length of complete, decodable
serialized output. Payload-only measurements must be explicitly labelled.
