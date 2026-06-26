param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Join-Path $repoRoot "project"

if (-not (Test-Path $projectRoot)) {
  Write-Error "Missing project directory. Run this script from the repository root."
}

Set-Location $projectRoot

try {
  python -c "import uvicorn" 2>$null
} catch {
  Write-Host "Missing Python dependency: uvicorn. Install project dependencies first. This script will not install dependencies." -ForegroundColor Yellow
  exit 1
}

Write-Host "Starting backend: http://127.0.0.1:$Port/docs"
Write-Host "This script does not print .env or database connection strings."
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port

