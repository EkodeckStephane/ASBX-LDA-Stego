# Experiments

The current phase establishes a reference codec and correctness tests before
corpus-scale evaluation.

## Layout

- `src/asbc/`: reference implementation;
- `tests/`: round-trip, exact-cost, and malformed-stream tests;
- `config/`: pinned experiment settings;
- `scripts/`: data generation and evaluation;
- `reports/`: hypotheses, format notes, and protocol;
- `manifests/`: corpus provenance and hashes;
- `results/`: generated machine-readable results;
- `figures/`: generated exploratory figures.

## Native and large-corpus checks

The C implementation lives in `native/asbx_c`. It is exercised by
`tests/test_native_c.py`, including Python-to-C and C-to-Python compatibility.

For larger local throughput checks without committing bulky data:

```powershell
python experiments\scripts\generate_large_corpus.py
python experiments\scripts\run_large_native_benchmark.py
```

The generated payloads are deterministic and recorded in
`manifests/generated_large.csv`; the binary payload directory is ignored by Git.
