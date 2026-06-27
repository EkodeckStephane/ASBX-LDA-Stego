# ASBX C API

This directory contains the native C implementation of the experimental ASBX
format version `0`.

## Build

Windows with MSYS2 UCRT64:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Compiler matrix smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File build_matrix.ps1
```

Portable GCC-style build:

```sh
gcc -O3 -std=c11 -Wall -Wextra -pedantic asbx.c asbx_cli.c -o asbxc
```

## Library Surface

Include `asbx.h` and link `asbx.c`.

Primary functions:

- `asbx_default_config()`;
- `asbx_encode_with_config(...)`;
- `asbx_decode(...)`;
- `asbx_validate(...)`;
- `asbx_buffer_free(...)`;
- `asbx_format_version()`;
- `asbx_status_message(...)`.

The legacy convenience function `asbx_encode(...)` remains available for simple
callers.

## CLI

```powershell
.\asbxc.exe encode --block-size 256 input.bin output.asbx
.\asbxc.exe encode-oracle --block-size 256 input.bin output.asbx
.\asbxc.exe validate output.asbx
.\asbxc.exe decode output.asbx recovered.bin
.\asbxc.exe bench --block-size 256 200 input.bin
```

`bench` loads the input once, repeats in-memory encode/decode loops, verifies
round-trip recovery, and prints CSV-like key-value metrics.
