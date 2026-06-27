# Initial Experimental Protocol

1. Establish exhaustive round trips for all byte strings up to a tractable
   length and randomized larger inputs.
2. Verify that the analytical cost API equals actual serialized bytes.
3. Generate controlled synthetic files with independent factors for zero-block
   fraction, boundary zeros, Hamming weight, clustering, run length, noise,
   block size, and distribution shift.
4. Split real data by file, never by randomly sampled blocks.
5. Compare raw, each fixed mode, best fixed mode, exact oracle, deterministic
   selector, and relevant general and specialized codecs.
6. Report file-level observations, weighted aggregates, medians, bootstrap
   intervals, effect sizes, and multiplicity-corrected paired tests.
7. Attempt machine learning only after deterministic regret is measured.

## Selector freeze

The deterministic selector uses zero-byte boundaries, Hamming weight, and
one-bit run count. Its rules were frozen after synthetic train/validation
analysis. Real-domain test files may be used for evaluation but not tuning.
