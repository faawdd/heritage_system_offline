param(
    [string]$OutputRoot = "desktop_runtime"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

$pythonExe = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $pythonExe = ".venv\Scripts\python.exe"
}

Write-Host "[desktop-runtime] Installing build tools..."
& $pythonExe -m pip install --upgrade pip pyinstaller

Write-Host "[desktop-runtime] Building backend executable..."
& $pythonExe -m PyInstaller `
    desktop_backend.py `
    --name heritage_backend `
    --noconfirm `
    --clean `
    --onedir

$outputDir = Join-Path $projectRoot $OutputRoot
$backendDir = Join-Path $outputDir "backend"

if (Test-Path $outputDir) {
    Remove-Item -Path $outputDir -Recurse -Force
}

New-Item -ItemType Directory -Path $backendDir | Out-Null

Copy-Item -Path "dist\heritage_backend\*" -Destination $backendDir -Recurse -Force
Copy-Item -Path "db.sqlite3" -Destination $backendDir -Force
if (Test-Path "media") { Copy-Item -Path "media" -Destination $backendDir -Recurse -Force }
if (Test-Path "static") { Copy-Item -Path "static" -Destination $backendDir -Recurse -Force }
if (Test-Path "templates") { Copy-Item -Path "templates" -Destination $backendDir -Recurse -Force }
if (Test-Path ".env") { Copy-Item -Path ".env" -Destination $backendDir -Force }

Write-Host "[desktop-runtime] Backend runtime is ready: $backendDir"
Write-Host "[desktop-runtime] Next: cd frontend ; npm run desktop:pack"
