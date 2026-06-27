# ML and Neural Selector Verdict

The codec modes, serialization, and decoder are unchanged. Models only
replace the encoder-side mode decision. Training uses real training
files; evaluation uses the untouched real test files.

| Model | Dataset | ML ratio | Gain vs rule | Regret vs oracle | Model bytes | Net bytes after charging model once |
|---|---|---:|---:|---:|---:|---:|
| decision_tree | SuiteSparse_HB_bcsstk | 0.155964 | -0.029% | 0.119% | 8186 | -8200 |
| decision_tree | fashion_mnist | 0.875612 | 0.548% | 0.009% | 8186 | 29613 |
| decision_tree | mnist | 0.641152 | 1.752% | 0.032% | 8186 | 81431 |
| hist_gradient_boosting | SuiteSparse_HB_bcsstk | 0.155808 | 0.072% | 0.018% | 452981 | -452946 |
| hist_gradient_boosting | fashion_mnist | 0.875561 | 0.553% | 0.003% | 452981 | -414780 |
| hist_gradient_boosting | mnist | 0.640974 | 1.779% | 0.004% | 452981 | -361967 |
| small_mlp | SuiteSparse_HB_bcsstk | 0.155779 | 0.090% | 0.000% | 48532 | -48488 |
| small_mlp | fashion_mnist | 0.876570 | 0.439% | 0.118% | 48532 | -18244 |
| small_mlp | mnist | 0.641775 | 1.656% | 0.129% | 48532 | 36200 |

## Runtime

- Deterministic features: 148.3 us/block.
- ML features: 332.3 us/block.
- `decision_tree` prediction only: 0.13 us/block.
- `hist_gradient_boosting` prediction only: 9.71 us/block.
- `small_mlp` prediction only: 0.68 us/block.

## Decision

The small decision tree is the practical ML candidate. It captures most
of the available improvement with an 8 kB model and negligible
prediction time. Histogram gradient boosting is closest to the oracle
but its 453 kB model is not justified for these corpus sizes. The small
neural network is larger and less accurate than the tree, so deeper
learning is not justified by the current evidence.

ML improves mode selection but does not change the broader codec verdict:
general-purpose codecs remain much smaller on these datasets. ML should
remain an optional encoder-side selector, not the central compression
claim.
