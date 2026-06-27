# Native ASBX Implementation

`asbx_c/` contains a C implementation of the ASBX v0 container format.

Implemented:

- deterministic non-oracle selector;
- exact oracle selector for comparison;
- all seven ASBX block modes;
- canonical unsigned LEB128 decoding;
- global raw fallback matching the Python reference;
- public C API with explicit configuration and container statistics;
- CLI commands for encode, validate, decode, bounded decode, oracle encode, and in-process benchmark.

Build on Windows with MSYS2 UCRT64:

```powershell
powershell -ExecutionPolicy Bypass -File experiments\native\asbx_c\build.ps1
```

CLI usage:

```powershell
experiments\native\asbx_c\asbxc.exe encode --block-size 256 input.bin output.asbx
experiments\native\asbx_c\asbxc.exe validate output.asbx
experiments\native\asbx_c\asbxc.exe decode output.asbx recovered.bin
experiments\native\asbx_c\asbxc.exe decode-limited 1048576 output.asbx recovered.bin
experiments\native\asbx_c\asbxc.exe bench --block-size 256 200 input.bin
```

Multi-compiler smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File experiments\native\asbx_c\build_matrix.ps1
```

Cross-compatibility with the Python implementation is covered by
`experiments/tests/test_native_c.py`.
