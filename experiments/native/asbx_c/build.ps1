#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Gcc = "C:\msys64\ucrt64\bin\gcc.exe"
if (-not (Test-Path $Gcc)) {
    throw "MSYS2 UCRT64 gcc not found at $Gcc"
}

Push-Location $Here
try {
    & $Gcc -O3 -std=c11 -Wall -Wextra -pedantic -c asbx.c -o asbx.o
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Gcc -O3 -std=c11 -Wall -Wextra -pedantic -c asbx_cli.c -o asbx_cli.o
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Gcc -O3 -std=c11 -Wall -Wextra -pedantic asbx.o asbx_cli.o -o asbxc.exe
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Built $Here\asbxc.exe"
} finally {
    Pop-Location
}
