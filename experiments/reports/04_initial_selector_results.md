# Initial Deterministic Selector Results

These results are exploratory and use only deterministic synthetic files.
They are not evidence of performance on real application domains.

## Held-out aggregate

- Test files: 9.
- Original bytes: 294912.
- Exact-oracle ratio: 0.257616.
- Deterministic-selector ratio: 0.257857.
- Aggregate regret: 71 bytes (0.0241%).
- Largest file-level regret: sparse_bits_001 at 0.1526%.

The working median/aggregate regret target is met, but the tail-regret
target is not yet met because clustered set bits remain difficult.

## Per-scenario results

| Scenario | Oracle ratio | Selector ratio | Regret bytes | Train-selected fixed | Fixed test ratio |
|---|---:|---:|---:|---|---:|
| all_one | 0.019928 | 0.019928 | 0 | fixed_zero_gaps | 0.019928 |
| all_zero | 0.016022 | 0.016022 | 0 | fixed_zero | 0.016022 |
| boundary_zeros | 0.526428 | 0.527039 | 20 | fixed_zero_trim | 0.526428 |
| clustered_bits | 0.160919 | 0.160950 | 1 | fixed_zero_trim | 0.189087 |
| dense_bits_99 | 0.119690 | 0.119690 | 0 | fixed_zero_gaps | 0.119690 |
| random | 1.000275 | 1.000275 | 0 | fixed_raw | 1.000275 |
| sparse_bits_001 | 0.032898 | 0.034424 | 50 | fixed_one_gaps | 0.033417 |
| sparse_bits_01 | 0.120483 | 0.120483 | 0 | fixed_one_gaps | 0.120483 |
| zero_blocks_75 | 0.321899 | 0.321899 | 0 | fixed_zero | 0.321899 |

## Largest block-level mistakes

| Scenario | Oracle mode | Selected mode | Blocks | Regret bytes |
|---|---|---|---:|---:|
| sparse_bits_001 | one_gaps | zero_trim | 46 | 50 |
| boundary_zeros | zero_trim | one_gaps | 2 | 20 |
| clustered_bits | one_gaps | zero_trim | 1 | 1 |

## Interpretation

The run-structure feature removes nearly all regret on clustered-bit
files while preserving exact decisions on the dense, random, and
zero-block controls. The remaining mistakes are small boundary cases
between zero trimming and one-position gaps.

No machine-learning experiment is justified at this stage. The next
required step is evaluation on real held-out files. The deterministic
rule is frozen for that evaluation; it must not be retuned on test
files.
