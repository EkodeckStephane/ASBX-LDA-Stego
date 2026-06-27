# SPE - ASBX Sparse Codec and LDA Capacity Case Study

This directory contains the Software: Practice and Experience submission
artefacts for:

> **ASBX: A Reproducible Adaptive Sparse Block Codec with an LDA
> Steganography Capacity Case Study**

The intended SPE positioning is implementation-oriented: ASBX is the primary
software artefact; the LDA component is a reproducible capacity case study,
not a complete deployable stegosystem.

---

## Structure

```text
SPE/
  LDA_Stego_ASBX/           LaTeX manuscript
    main.tex
    references.bib
    RESULT_TRACEABILITY.md
    figures/
      Figure_1_pipeline.tex
      fig_stego_capacity.pdf
      fig_stego_density.pdf
      fig_stego_bars.pdf
      fig_asbx_*.pdf
    tables/
      tab_practical_benchmark.tex
      tab_asbx_*.tex

  code/                      Python implementation and reproducibility scripts
    payload_encoder.py
    payload_decoder.py
    stego_generator.py
    capacity_benchmark.py
    software_benchmark.py
    native_benchmark.py
    block_size_sweep.py
    practical_benchmark.py
    produce_figures.py
    test_integration.py
    requirements.txt

  results/                   Generated machine-readable outputs
    capacity_results.csv
    capacity_results.json
    software_benchmark.csv
    software_benchmark_summary.csv
    native_benchmark.csv
    native_benchmark_summary.csv
    block_size_sweep.csv
    block_size_sweep_summary.csv
    practical_benchmark.csv
    practical_benchmark_summary.csv

  run_reproducibility.ps1    One-command Windows reproducibility script
```

---

## Quick Start

Install the Python dependencies:

```powershell
pip install numpy matplotlib gensim
```

For the exact tested ranges, use:

```powershell
pip install -r SPE\code\requirements.txt
```

From the repository root, reproduce the SPE artefacts:

```powershell
.\SPE\run_reproducibility.ps1
```

If Windows blocks local PowerShell scripts, run the equivalent one-off bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\SPE\run_reproducibility.ps1
```

The script runs integration tests, the 51-payload capacity benchmark, the
57-payload broad software benchmark, the full-corpus block-size sweep, the
native C benchmark, the short memory-oriented practical benchmark, and
figure/table generation.

Compile the article:

```powershell
cd SPE\LDA_Stego_ASBX
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Requires a standard LaTeX distribution with `amsmath`, `booktabs`,
`algorithm`, `algpseudocode`, `microtype`, `natbib`, and `lmodern`.

---

## Current Results

| Domain | ASBX ratio | Capacity gain |
|---|---:|---:|
| Sparse matrices (SuiteSparse bcsstk10-12) | 0.083 mean | x12.8 |
| Image tensors (KMNIST) | 0.648 mean | x1.54 |
| Text controls (Canterbury, Silesia) | about 1.00 after exclusions | x1.0 |

All 51 steganographic encode-decode round-trips are byte-exact.

The broad software benchmark confirms that the deterministic selector closely
tracks the ASBX oracle, but also that zstd/Brotli/LZMA usually outperform ASBX
on short general-purpose prefixes.  ASBX is therefore positioned as a
byte-specified sparse-structure codec and reproducible selector artefact, not
as a universal compressor.

The native C implementation lives under `experiments/native/asbx_c/` and
builds with MSYS2 UCRT64.  It provides encode/decode/validate/bounded-decode
CLI commands plus an explicit C API.  Its benchmark uses repeated in-memory
loops and shows one-to-two orders of magnitude faster encoding than the Python
reference on the local 16 KiB prefixes.

---

## Core Capacity Principle

```text
secret bytes
  -> ASBX compress, ratio R
  -> compressed bytes
  -> chunk into k-bit topic indices, k = floor(log2 T)
  -> embed one topic index per stego word

Capacity gain = 1 / R
```

For sparse matrices with mean `R = 0.083`, the same cover capacity embeds
about 12.8 times more original data than raw byte embedding.  For ordinary text
payloads, `R` is approximately 1 and the gain disappears.

---

## Submission Notes

- Primary contribution: byte-specified, tested, reproducible ASBX codec.
- Practical software contribution: deterministic non-oracle selector with
  measured regret against the exact oracle.
- Native implementation contribution: C encoder/decoder and CLI compatible
  with the Python ASBX container format.
- Case study: ASBX pre-compression for LDA topic-index embedding capacity.
- Explicit non-claims: universal compression-ratio superiority, stable ASBX v1
  standardisation, and end-to-end steganographic security.
- Wiley data-sharing alignment: generated results, scripts, code, and tables
  are available in this repository and should be archived with a persistent
  identifier before submission.
