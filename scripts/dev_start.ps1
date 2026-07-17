param(
  [int]$BackendPort = 18080,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendScript = Join-Path $PSScriptRoot "dev_start_backend.ps1"
$frontendScript = Join-Path $PSScriptRoot "dev_start_frontend.ps1"

if (-not (Test-Path $backendScript) -or -not (Test-Path $frontendScript)) {
  Write-Error "Missing dev start script."
}

Write-Host "Starting backend and frontend in two PowerShell windows."
Write-Host "Backend: http://127.0.0.1:$BackendPort/docs"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "If port $BackendPort is occupied, use: .\scripts\dev_start.ps1 -BackendPort 18081"

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`"", "-Port", "$BackendPort" -WorkingDirectory $repoRoot -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$frontendScript`"", "-Port", "$FrontendPort" -WorkingDirectory $repoRoot -WindowStyle Normal
