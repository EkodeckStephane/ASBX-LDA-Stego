$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$candidates = @()

$gcc = Get-Command gcc -ErrorAction SilentlyContinue
if ($gcc) {
    $candidates += @{
        Name = "path-gcc"
        Compile = @("gcc", "-O3", "-std=c11", "-Wall", "-Wextra", "-pedantic", "asbx.c", "asbx_cli.c", "-o", "asbxc-gcc.exe")
        Exe = ".\asbxc-gcc.exe"
    }
}

$clang = Get-Command clang -ErrorAction SilentlyContinue
if ($clang) {
    $candidates += @{
        Name = "path-clang"
        Compile = @("clang", "-O3", "-std=c11", "-Wall", "-Wextra", "-pedantic", "asbx.c", "asbx_cli.c", "-o", "asbxc-clang.exe")
        Exe = ".\asbxc-clang.exe"
    }
}

$msysBash = "C:\msys64\usr\bin\bash.exe"
if (Test-Path $msysBash) {
    $msysPath = "/" + ($scriptDir.Substring(0, 1).ToLower()) + $scriptDir.Substring(2).Replace("\", "/")
    $candidates += @{
        Name = "msys2-ucrt64-gcc"
        Bash = "export PATH=/ucrt64/bin:/usr/bin:`$PATH; cd '$msysPath' && gcc -O3 -std=c11 -Wall -Wextra -pedantic asbx.c asbx_cli.c -o asbxc-msys2-ucrt64.exe"
        Exe = ".\asbxc-msys2-ucrt64.exe"
    }
}

if ($candidates.Count -eq 0) {
    throw "No C compiler candidate found. Install GCC, Clang, or MSYS2 UCRT64."
}

$input = Join-Path $scriptDir "build-matrix-input.bin"
$encoded = Join-Path $scriptDir "build-matrix-output.asbx"
$decoded = Join-Path $scriptDir "build-matrix-decoded.bin"
[byte[]]$payload = 0..255
[System.IO.File]::WriteAllBytes($input, $payload)

foreach ($candidate in $candidates) {
    Write-Host "== $($candidate.Name)"
    if ($candidate.ContainsKey("Bash")) {
        & $msysBash -lc $candidate.Bash
    } else {
        $cmd = $candidate.Compile[0]
        $args = @($candidate.Compile[1..($candidate.Compile.Count - 1)])
        & $cmd @args
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $candidate.Exe encode --block-size 64 $input $encoded
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $candidate.Exe validate $encoded
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $candidate.Exe decode $encoded $decoded
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $a = [System.IO.File]::ReadAllBytes($input)
    $b = [System.IO.File]::ReadAllBytes($decoded)
    if (-not [System.Linq.Enumerable]::SequenceEqual($a, $b)) {
        throw "Round-trip mismatch for $($candidate.Name)"
    }
}

Remove-Item -LiteralPath $input, $encoded, $decoded -Force
Write-Host "Build matrix passed."
