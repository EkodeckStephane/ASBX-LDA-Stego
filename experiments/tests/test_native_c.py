import subprocess
from pathlib import Path
import random

import pytest

from asbc import decode, encode_deterministic


ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "experiments" / "native" / "asbx_c"
EXE = NATIVE / ("asbxc.exe")


@pytest.fixture(scope="session")
def asbxc() -> Path:
    sources = list(NATIVE.glob("*.c")) + list(NATIVE.glob("*.h")) + [NATIVE / "Makefile", NATIVE / "build.ps1"]
    stale = EXE.exists() and any(path.exists() and path.stat().st_mtime > EXE.stat().st_mtime for path in sources)
    if not EXE.exists() or stale:
        build = NATIVE / "build.ps1"
        if build.exists():
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(build)],
                check=True,
                cwd=NATIVE,
            )
    if not EXE.exists():
        pytest.skip("native ASBX C CLI is not built")
    return EXE


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\x00" * 4096,
        b"\xff" * 4096,
        b"\x00" * 256 + b"payload" * 20 + b"\x00" * 128,
        bytes(range(256)) * 8,
    ],
)
def test_native_c_round_trip(tmp_path: Path, asbxc: Path, payload: bytes) -> None:
    src = tmp_path / "input.bin"
    enc = tmp_path / "encoded.asbx"
    out = tmp_path / "decoded.bin"
    src.write_bytes(payload)

    subprocess.run([str(asbxc), "encode", "--block-size", "256", str(src), str(enc)], check=True)
    subprocess.run([str(asbxc), "decode", str(enc), str(out)], check=True)

    assert out.read_bytes() == payload


def test_native_c_decodes_python_container(tmp_path: Path, asbxc: Path) -> None:
    payload = b"\x00" * 1024 + bytes(range(256)) + b"\xff" * 512
    enc = tmp_path / "python.asbx"
    out = tmp_path / "decoded.bin"
    enc.write_bytes(encode_deterministic(payload, block_size=128))

    subprocess.run([str(asbxc), "decode", str(enc), str(out)], check=True)

    assert out.read_bytes() == payload


def test_python_decodes_native_c_container(tmp_path: Path, asbxc: Path) -> None:
    payload = b"\x00" * 512 + b"native-c" * 50 + b"\x00" * 512
    src = tmp_path / "input.bin"
    enc = tmp_path / "native.asbx"
    src.write_bytes(payload)

    subprocess.run([str(asbxc), "encode", "--block-size", "128", str(src), str(enc)], check=True)

    assert decode(enc.read_bytes()) == payload


def test_native_c_validate_reports_container_stats(tmp_path: Path, asbxc: Path) -> None:
    payload = b"\x00" * 2048 + b"validate" * 32
    src = tmp_path / "input.bin"
    enc = tmp_path / "native.asbx"
    src.write_bytes(payload)

    subprocess.run([str(asbxc), "encode", "--block-size", "128", str(src), str(enc)], check=True)
    proc = subprocess.run(
        [str(asbxc), "validate", str(enc)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "format_version=0" in proc.stdout
    assert f"input_bytes={len(payload)}" in proc.stdout
    assert "encoded_bytes=" in proc.stdout


def test_native_c_decode_limit_fails_closed(tmp_path: Path, asbxc: Path) -> None:
    payload = b"\x00" * 1024
    src = tmp_path / "input.bin"
    enc = tmp_path / "native.asbx"
    out = tmp_path / "decoded.bin"
    src.write_bytes(payload)

    subprocess.run([str(asbxc), "encode", "--block-size", "128", str(src), str(enc)], check=True)
    proc = subprocess.run(
        [str(asbxc), "decode-limited", "512", str(enc), str(out)],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert not out.exists()


def test_native_c_rejects_corrupted_containers(tmp_path: Path, asbxc: Path) -> None:
    payload = b"\x00" * 512 + b"corruption-test" * 16
    src = tmp_path / "input.bin"
    enc = tmp_path / "native.asbx"
    src.write_bytes(payload)
    subprocess.run([str(asbxc), "encode", "--block-size", "64", str(src), str(enc)], check=True)
    original = bytearray(enc.read_bytes())

    for offset in [0, 1, 4, 5, 6]:
        corrupted = bytearray(original)
        corrupted[offset] ^= 0x55
        bad = tmp_path / f"bad_{offset}.asbx"
        bad.write_bytes(corrupted)
        proc = subprocess.run([str(asbxc), "validate", str(bad)], capture_output=True, text=True)
        assert proc.returncode != 0

    truncated = tmp_path / "truncated.asbx"
    truncated.write_bytes(original[:-1])
    proc = subprocess.run([str(asbxc), "validate", str(truncated)], capture_output=True, text=True)
    assert proc.returncode != 0


def test_native_c_deterministic_fuzz_round_trips(tmp_path: Path, asbxc: Path) -> None:
    rng = random.Random(20260627)
    for case in range(25):
        size = rng.randrange(0, 4096)
        payload = bytes(rng.randrange(0, 256) if rng.random() < 0.08 else 0 for _ in range(size))
        src = tmp_path / f"fuzz_{case}.bin"
        enc = tmp_path / f"fuzz_{case}.asbx"
        out = tmp_path / f"fuzz_{case}.out"
        src.write_bytes(payload)

        subprocess.run([str(asbxc), "encode", "--block-size", "128", str(src), str(enc)], check=True)
        subprocess.run([str(asbxc), "decode-limited", str(max(size, 1)), str(enc), str(out)], check=True)

        assert out.read_bytes() == payload
