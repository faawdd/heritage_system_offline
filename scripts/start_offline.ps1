param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$InitDeps
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in PATH."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[offline] Creating virtual environment (.venv)..."
    python -m venv .venv
}

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "[offline] Upgrading pip..."
& $pythonExe -m pip install --upgrade pip

if ($InitDeps) {
    Write-Host "[offline] Installing dependencies from requirements.txt..."
    & $pythonExe -m pip install -r requirements.txt
}

$env:DJANGO_DEBUG = "1"
$env:DJANGO_FORCE_HTTPS = "0"
$env:DJANGO_WEB_BASE_URL = "http://${BindHost}:${Port}"

Write-Host "[offline] Running database migrations..."
& $pythonExe manage.py migrate --noinput

$url = "http://${BindHost}:${Port}/"
Write-Host "[offline] Opening browser: $url"
Start-Process $url | Out-Null

Write-Host "[offline] Starting Django server at ${BindHost}:${Port}"
& $pythonExe manage.py runserver "${BindHost}:${Port}"
