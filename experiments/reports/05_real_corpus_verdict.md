# Preliminary Verdict on Real Files

This evaluation uses complete Canterbury files and the fixed 64 KiB
prefixes of all Silesia files. The inputs are real public-corpus files,
not generated data. Silesia prefixes remain exploratory; complete
Silesia evaluation is still required.

| Corpus | Method | Files | Weighted ratio |
|---|---|---:|---:|
| canterbury | asbx_deterministic | 11 | 0.887873 |
| canterbury | asbx_fixed_one_gaps | 11 | 0.893982 |
| canterbury | asbx_fixed_raw | 11 | 1.000034 |
| canterbury | asbx_fixed_zero | 11 | 0.972263 |
| canterbury | asbx_fixed_zero_gaps | 11 | 1.000034 |
| canterbury | asbx_fixed_zero_trim | 11 | 0.931495 |
| canterbury | asbx_oracle | 11 | 0.887113 |
| canterbury | bzip2_9 | 11 | 0.193081 |
| canterbury | lzma_9 | 11 | 0.175138 |
| canterbury | zlib_9 | 11 | 0.258938 |
| silesia_sample | asbx_deterministic | 12 | 0.943804 |
| silesia_sample | asbx_fixed_one_gaps | 12 | 0.944037 |
| silesia_sample | asbx_fixed_raw | 12 | 1.000137 |
| silesia_sample | asbx_fixed_zero | 12 | 0.960592 |
| silesia_sample | asbx_fixed_zero_gaps | 12 | 1.000137 |
| silesia_sample | asbx_fixed_zero_trim | 12 | 0.951302 |
| silesia_sample | asbx_oracle | 12 | 0.939693 |
| silesia_sample | bzip2_9 | 12 | 0.326756 |
| silesia_sample | lzma_9 | 12 | 0.318049 |
| silesia_sample | zlib_9 | 12 | 0.369737 |

## Verdict

- `canterbury`: oracle `0.887113`, selector `0.887873`, best fixed ASBX `0.893982`, best tested general codec `0.175138`.
- `silesia_sample`: oracle `0.939693`, selector `0.943804`, best fixed ASBX `0.944037`, best tested general codec `0.318049`.

The project has not yet met its continuation criterion. These general
corpora are controls rather than the target sparse application domains.
A positive article claim requires at least two real sparse-domain
datasets and held-out file-level validation. The current result can
support only a preliminary engineering verdict.
