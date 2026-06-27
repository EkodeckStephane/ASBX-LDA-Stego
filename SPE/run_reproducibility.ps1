#Requires -Version 5.1
<#
.SYNOPSIS
    Full reproducibility script for ASBX-LDA Text Steganography (SPE article).

.DESCRIPTION
    Runs, in order:
      1. Integration tests (17 checks)
      2. Capacity benchmark (51 payloads)
      3. Broad software benchmark
      4. Full-corpus block-size sweep
      5. Native C benchmark
      6. Practical memory benchmark
      7. Figure generation

    All steps must pass before figures are generated.
    Run from the ASBX repository root:

        .\SPE\run_reproducibility.ps1

.NOTES
    Requires: Python 3.11+, numpy, matplotlib.
    ASBX codec must be present in experiments\src\asbc\.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$CodeDir  = Join-Path $PSScriptRoot "code"
$Python   = "python"

function Write-Step { param([string]$Msg) Write-Host "`n=== $Msg ===" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Msg) Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Write-Fail { param([string]$Msg) Write-Host "  [FAIL] $Msg" -ForegroundColor Red }

Push-Location $RepoRoot
try {
    # -----------------------------------------------------------------------
    # Step 1: Integration tests
    # -----------------------------------------------------------------------
    Write-Step "Step 1 of 7: Integration tests"
    & $Python (Join-Path $CodeDir "test_integration.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Integration tests failed. Aborting."
        exit 1
    }
    Write-Ok "All integration tests passed."

    # -----------------------------------------------------------------------
    # Step 2: Capacity benchmark
    # -----------------------------------------------------------------------
    Write-Step "Step 2 of 7: Capacity benchmark (51 payloads)"
    & $Python (Join-Path $CodeDir "capacity_benchmark.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Capacity benchmark failed. Aborting."
        exit 1
    }
    $CsvPath = Join-Path $PSScriptRoot "results\capacity_results.csv"
    if (-not (Test-Path $CsvPath)) {
        Write-Fail "Expected output not found: $CsvPath"
        exit 1
    }
    Write-Ok "Benchmark complete. Results in SPE\results\"

    # -----------------------------------------------------------------------
    # Step 3: Broad software benchmark
    # -----------------------------------------------------------------------
    Write-Step "Step 3 of 7: Broad software benchmark"
    & $Python (Join-Path $CodeDir "software_benchmark.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Broad software benchmark failed. Aborting."
        exit 1
    }
    $SoftwareCsvPath = Join-Path $PSScriptRoot "results\software_benchmark_summary.csv"
    if (-not (Test-Path $SoftwareCsvPath)) {
        Write-Fail "Expected output not found: $SoftwareCsvPath"
        exit 1
    }
    Write-Ok "Broad software benchmark complete. Results in SPE\results\"

    # -----------------------------------------------------------------------
    # Step 4: Full-corpus block-size sweep
    # -----------------------------------------------------------------------
    Write-Step "Step 4 of 7: Full-corpus block-size sweep"
    & $Python (Join-Path $CodeDir "block_size_sweep.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Block-size sweep failed. Aborting."
        exit 1
    }
    $SweepCsvPath = Join-Path $PSScriptRoot "results\block_size_sweep_summary.csv"
    if (-not (Test-Path $SweepCsvPath)) {
        Write-Fail "Expected output not found: $SweepCsvPath"
        exit 1
    }
    Write-Ok "Block-size sweep complete. Results in SPE\results\"

    # -----------------------------------------------------------------------
    # Step 5: Native C benchmark
    # -----------------------------------------------------------------------
    Write-Step "Step 5 of 7: Native C benchmark"
    & $Python (Join-Path $CodeDir "native_benchmark.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Native C benchmark failed. Aborting."
        exit 1
    }
    $NativeCsvPath = Join-Path $PSScriptRoot "results\native_benchmark_summary.csv"
    if (-not (Test-Path $NativeCsvPath)) {
        Write-Fail "Expected output not found: $NativeCsvPath"
        exit 1
    }
    Write-Ok "Native C benchmark complete. Results in SPE\results\"

    # -----------------------------------------------------------------------
    # Step 6: Practical benchmark
    # -----------------------------------------------------------------------
    Write-Step "Step 6 of 7: Practical memory benchmark"
    & $Python (Join-Path $CodeDir "practical_benchmark.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Practical benchmark failed. Aborting."
        exit 1
    }
    $PracticalCsvPath = Join-Path $PSScriptRoot "results\practical_benchmark_summary.csv"
    if (-not (Test-Path $PracticalCsvPath)) {
        Write-Fail "Expected output not found: $PracticalCsvPath"
        exit 1
    }
    Write-Ok "Practical benchmark complete. Results in SPE\results\"

    # -----------------------------------------------------------------------
    # Step 7: Figures
    # -----------------------------------------------------------------------
    Write-Step "Step 7 of 7: Figure generation"
    & $Python (Join-Path $CodeDir "produce_figures.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Figure generation failed."
        exit 1
    }

    $Figures = @(
        "SPE\LDA_Stego_ASBX\figures\fig_stego_capacity.pdf",
        "SPE\LDA_Stego_ASBX\figures\fig_stego_density.pdf",
        "SPE\LDA_Stego_ASBX\figures\fig_stego_bars.pdf"
    )
    foreach ($fig in $Figures) {
        $full = Join-Path $RepoRoot $fig
        if (Test-Path $full) {
            Write-Ok $fig
        } else {
            Write-Fail "Missing: $fig"
            exit 1
        }
    }

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    Write-Host "`n=======================================" -ForegroundColor Cyan
    Write-Host "Reproducibility check PASSED." -ForegroundColor Green
    Write-Host "All results are in SPE\results\ and SPE\LDA_Stego_ASBX\figures\." -ForegroundColor Green
    Write-Host "=======================================`n" -ForegroundColor Cyan

} finally {
    Pop-Location
}
