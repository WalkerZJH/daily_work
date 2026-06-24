$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendScript = Join-Path $PSScriptRoot "dev_start_backend.ps1"
$frontendScript = Join-Path $PSScriptRoot "dev_start_frontend.ps1"

if (-not (Test-Path $backendScript) -or -not (Test-Path $frontendScript)) {
  Write-Error "启动脚本缺失。"
}

Write-Host "将启动两个 PowerShell 窗口：后端与前端。"
Write-Host "后端地址: http://127.0.0.1:8000/docs"
Write-Host "前端地址: http://127.0.0.1:5173"

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`"" -WorkingDirectory $repoRoot -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$frontendScript`"" -WorkingDirectory $repoRoot -WindowStyle Normal
