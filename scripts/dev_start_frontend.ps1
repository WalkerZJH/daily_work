param(
  [int]$Port = 5173
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "front_end"

if (-not (Test-Path $frontendRoot)) {
  Write-Error "未找到 front_end 目录。请在仓库根目录运行脚本。"
}

Set-Location $frontendRoot

if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
  Write-Host "缺少 node_modules。请先运行 npm install；本脚本不会自动安装依赖。" -ForegroundColor Yellow
  exit 1
}

Write-Host "启动前端: http://127.0.0.1:$Port"
npm run dev -- --host 127.0.0.1 --port $Port

