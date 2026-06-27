import subprocess
from pathlib import Path

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
