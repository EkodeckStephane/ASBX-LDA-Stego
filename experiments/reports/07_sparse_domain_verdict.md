# Verdict on Real Sparse Domains

All rows use held-out source test partitions. The ASBX selector was frozen
before these files were prepared or measured.

| Domain | Dataset | Method | Files | Weighted ratio |
|---|---|---|---:|---:|
| grayscale_image_tensor | fashion_mnist | asbx_deterministic | 10 | 0.880434 |
| grayscale_image_tensor | fashion_mnist | asbx_fixed_one_gaps | 10 | 0.950329 |
| grayscale_image_tensor | fashion_mnist | asbx_fixed_raw | 10 | 1.000011 |
| grayscale_image_tensor | fashion_mnist | asbx_fixed_zero | 10 | 1.000011 |
| grayscale_image_tensor | fashion_mnist | asbx_fixed_zero_gaps | 10 | 1.000011 |
| grayscale_image_tensor | fashion_mnist | asbx_fixed_zero_trim | 10 | 0.887486 |
| grayscale_image_tensor | fashion_mnist | asbx_oracle | 10 | 0.875535 |
| grayscale_image_tensor | fashion_mnist | bzip2_9 | 10 | 0.516781 |
| grayscale_image_tensor | fashion_mnist | lzma_9 | 10 | 0.482502 |
| grayscale_image_tensor | fashion_mnist | png_per_image | 10 | 0.648374 |
| grayscale_image_tensor | fashion_mnist | zlib_9 | 10 | 0.559149 |
| grayscale_image_tensor | mnist | asbx_deterministic | 10 | 0.652582 |
| grayscale_image_tensor | mnist | asbx_fixed_one_gaps | 10 | 0.763187 |
| grayscale_image_tensor | mnist | asbx_fixed_raw | 10 | 1.000011 |
| grayscale_image_tensor | mnist | asbx_fixed_zero | 10 | 0.991847 |
| grayscale_image_tensor | mnist | asbx_fixed_zero_gaps | 10 | 1.000011 |
| grayscale_image_tensor | mnist | asbx_fixed_zero_trim | 10 | 0.684315 |
| grayscale_image_tensor | mnist | asbx_oracle | 10 | 0.640946 |
| grayscale_image_tensor | mnist | bzip2_9 | 10 | 0.182846 |
| grayscale_image_tensor | mnist | lzma_9 | 10 | 0.179363 |
| grayscale_image_tensor | mnist | png_per_image | 10 | 0.350208 |
| grayscale_image_tensor | mnist | zlib_9 | 10 | 0.204429 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_deterministic | 3 | 0.155919 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_fixed_one_gaps | 3 | 0.156149 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_fixed_raw | 3 | 1.000086 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_fixed_zero | 3 | 1.000086 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_fixed_zero_gaps | 3 | 1.000086 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_fixed_zero_trim | 3 | 0.706641 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | asbx_oracle | 3 | 0.155779 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | bzip2_9 | 3 | 0.038705 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | lzma_9 | 3 | 0.037657 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | sparse_position_gaps | 3 | 0.138369 |
| sparse_matrix_pattern | SuiteSparse_HB_bcsstk | zlib_9 | 3 | 0.045579 |

## Decision evidence

- `fashion_mnist`: selector `0.880434`, oracle `0.875535`, best fixed ASBX `0.887486`, best external baseline `0.482502`.
- `mnist`: selector `0.652582`, oracle `0.640946`, best fixed ASBX `0.684315`, best external baseline `0.179363`.
- `SuiteSparse_HB_bcsstk`: selector `0.155919`, oracle `0.155779`, best fixed ASBX `0.156149`, best external baseline `0.037657`.

A continuation decision requires the adaptive selector to improve the
best fixed component on a real domain after complete costs. Competitive
positioning also requires comparison with the specialized baseline;
beating raw storage alone is insufficient.
