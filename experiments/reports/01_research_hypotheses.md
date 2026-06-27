# Preregistered Working Hypotheses

These hypotheses precede the main experiments and may be refined only with a
dated amendment.

## Primary endpoint

The primary metric is complete serialized bytes divided by original bytes,
paired by file. The primary comparison is the deterministic adaptive selector
against the best elementary fixed mode selected without test-file leakage.

## H1: adaptive selection

- Metric: paired complete-size difference per file.
- Comparator: best fixed elementary mode determined on training files.
- Test: paired bootstrap confidence interval and one-sided Wilcoxon test when
  its assumptions are defensible.
- Success: positive median saving, 95% confidence interval excluding zero,
  multiplicity-corrected `p < 0.05`, and at least 1% weighted byte reduction.
- Validation: held-out files from each real application domain.

## H2: positional sparsity

- Metric: complete record saving of one-position or zero-position mode.
- Comparator: raw record.
- Success: monotone relationship between favorable selection and the smaller
  of Hamming weight and its complement after controlling for block size.

## H3: zero structure

- Metric: contribution to complete byte saving.
- Comparator: adaptive codec without zero-block and zero-trim modes.
- Success: measured ablation with file-level uncertainty intervals.

## H4: alphabet granularity

- Metric: complete ratio and encode/decode throughput.
- Comparator: local, grouped, and global alphabets.
- Success: grouped alphabets improve a predeclared ratio-throughput objective
  on held-out files.

## H5: deterministic selector regret

- Metric: selector bytes minus exact-oracle bytes.
- Comparator: exact serialization oracle.
- Success: median regret below 0.5% of original bytes and bounded tail regret.

The deterministic rule was frozen after synthetic train/validation analysis.
No threshold may be changed after inspecting future real-domain test files.

## H6: optional learned selector

- Metric: complete ratio, decision time, throughput, and model bytes.
- Comparator: deterministic selector.
- Success: statistically significant held-out improvement that remains at
  least 0.5% after model and deployment costs.
