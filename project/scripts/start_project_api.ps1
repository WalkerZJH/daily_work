$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoRoot = Resolve-Path (Join-Path $projectRoot "..")
$batchRoot = Join-Path $repoRoot "data\project_result_batches"

if (-not (Test-Path $batchRoot)) {
  throw "RISK_RESULT_BATCH_ROOT does not exist: $batchRoot"
}

$env:RISK_RESULT_BATCH_ROOT = $batchRoot
$env:PYTHONPATH = [string]$repoRoot

Set-Location $projectRoot
& "C:\Users\admin\anaconda3\envs\ml\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 18080
