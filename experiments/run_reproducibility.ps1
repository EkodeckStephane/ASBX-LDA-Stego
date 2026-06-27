$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $root
Set-Location $project

python -m pytest experiments/tests -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python experiments/scripts/generate_synthetic_corpus.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python experiments/scripts/run_reference_campaign.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python experiments/scripts/run_selector_evaluation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python experiments/scripts/analyze_selector_blocks.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python experiments/scripts/summarize_selector.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
