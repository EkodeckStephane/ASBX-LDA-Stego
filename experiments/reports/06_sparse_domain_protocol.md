# Real Sparse-Domain Protocol

The domain choices and file splits were fixed before measuring ASBX ratios.

## Sparse matrix patterns

The matrices `HB/bcsstk01` through `HB/bcsstk09` come from the SuiteSparse
Matrix Collection and represent structural stiffness problems. The experiment
stores the exact binary sparsity pattern in row-major order with dimensions and
nonzero count. Numeric matrix values are excluded from this structural-pattern
experiment and must be evaluated separately before any claim about complete
sparse-matrix storage.

- Train: `bcsstk01` to `bcsstk03`.
- Validation: `bcsstk04` to `bcsstk06`.
- Test: `bcsstk07` to `bcsstk09`.

## Image tensors with zero backgrounds

MNIST and Fashion-MNIST image bytes are decoded from their official IDX gzip
archives without thresholding, normalization, cropping, or value changes.
Each prepared file contains 1,000 consecutive real images plus dimensions.

- Original training archives are training data.
- Original test archives are test data.
- Fashion-MNIST is reported separately from MNIST and serves as an
  out-of-dataset image-domain check.

## Licensing and redistribution

Downloaded archives and prepared files are excluded from version control.
The manifest records source URLs and hashes. Fashion-MNIST's official
repository states an MIT license. SuiteSparse matrix attribution is recorded,
but redistribution permission is not assumed. MNIST is treated as an external
research benchmark and is not redistributed.

## Frozen selector

The deterministic ASBX selector was frozen before these files were prepared or
measured. No selector threshold may be changed using their test results.

