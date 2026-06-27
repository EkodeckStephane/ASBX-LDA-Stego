# Downstream Transform Verdict

Each comparison uses the same downstream codec and held-out real files.
Every pipeline was decoded back to the exact original bytes.

| Dataset | Codec | Transform | Ratio | Difference vs raw codec | W/T/L | One-sided p |
|---|---|---|---:|---:|---:|---:|
| fashion_mnist | bzip2_9 | asbx_deterministic | 0.527554 | -84462 | 0/0/10 | 1 |
| fashion_mnist | bzip2_9 | asbx_oracle | 0.531086 | -112151 | 0/0/10 | 1 |
| fashion_mnist | bzip2_9 | raw | 0.516781 | 0 | 0/10/0 | 1 |
| fashion_mnist | lzma_9 | asbx_deterministic | 0.499354 | -132120 | 0/0/10 | 1 |
| fashion_mnist | lzma_9 | asbx_oracle | 0.503659 | -165872 | 0/0/10 | 1 |
| fashion_mnist | lzma_9 | raw | 0.482502 | 0 | 0/10/0 | 1 |
| fashion_mnist | zlib_9 | asbx_deterministic | 0.571580 | -97463 | 0/0/10 | 1 |
| fashion_mnist | zlib_9 | asbx_oracle | 0.576215 | -133798 | 0/0/10 | 1 |
| fashion_mnist | zlib_9 | raw | 0.559149 | 0 | 0/10/0 | 1 |
| mnist | bzip2_9 | asbx_deterministic | 0.199287 | -128903 | 0/0/10 | 1 |
| mnist | bzip2_9 | asbx_oracle | 0.205052 | -174101 | 0/0/10 | 1 |
| mnist | bzip2_9 | raw | 0.182846 | 0 | 0/10/0 | 1 |
| mnist | lzma_9 | asbx_deterministic | 0.198767 | -152128 | 0/0/10 | 1 |
| mnist | lzma_9 | asbx_oracle | 0.204735 | -198916 | 0/0/10 | 1 |
| mnist | lzma_9 | raw | 0.179363 | 0 | 0/10/0 | 1 |
| mnist | zlib_9 | asbx_deterministic | 0.221037 | -130212 | 0/0/10 | 1 |
| mnist | zlib_9 | asbx_oracle | 0.227708 | -182513 | 0/0/10 | 1 |
| mnist | zlib_9 | raw | 0.204429 | 0 | 0/10/0 | 1 |
| SuiteSparse_HB_bcsstk | bzip2_9 | asbx_deterministic | 0.047908 | -2880 | 0/0/3 | 1 |
| SuiteSparse_HB_bcsstk | bzip2_9 | asbx_oracle | 0.048036 | -2920 | 0/0/3 | 1 |
| SuiteSparse_HB_bcsstk | bzip2_9 | raw | 0.038705 | 0 | 0/3/0 | 1 |
| SuiteSparse_HB_bcsstk | lzma_9 | asbx_deterministic | 0.042923 | -1648 | 1/0/2 | 0.875 |
| SuiteSparse_HB_bcsstk | lzma_9 | asbx_oracle | 0.042962 | -1660 | 1/0/2 | 0.875 |
| SuiteSparse_HB_bcsstk | lzma_9 | raw | 0.037657 | 0 | 0/3/0 | 1 |
| SuiteSparse_HB_bcsstk | zlib_9 | asbx_deterministic | 0.047752 | -680 | 2/0/1 | 0.625 |
| SuiteSparse_HB_bcsstk | zlib_9 | asbx_oracle | 0.047816 | -700 | 2/0/1 | 0.625 |
| SuiteSparse_HB_bcsstk | zlib_9 | raw | 0.045579 | 0 | 0/3/0 | 1 |

## Decision

Neither the practical selector nor the exact oracle improves any tested downstream codec in aggregate. This rejects the current ASBX representation as a useful upstream transform.
