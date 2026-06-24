$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Join-Path $repoRoot "project"

if (-not (Test-Path $projectRoot)) {
  Write-Error "未找到 project 目录。请在仓库根目录运行脚本。"
}

Set-Location $projectRoot

try {
  python -c "import uvicorn" 2>$null
} catch {
  Write-Host "缺少 Python 后端依赖 uvicorn。请先在当前环境安装项目依赖，本脚本不会自动安装。" -ForegroundColor Yellow
  exit 1
}

Write-Host "启动后端: http://127.0.0.1:8000/docs"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

