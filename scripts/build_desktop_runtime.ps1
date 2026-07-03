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
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt
& $pythonExe -m pip install pyinstaller

Write-Host "[desktop-runtime] Building backend executable..."
& $pythonExe -m PyInstaller `
    desktop_backend.py `
    --name heritage_backend `
    --noconfirm `
    --clean `
    --onedir

$outputDir = Join-Path $projectRoot $OutputRoot
$appDir = Join-Path $outputDir "app"
$dataDir = Join-Path $outputDir "data"
$configDir = Join-Path $outputDir "config"

if (Test-Path $outputDir) {
    Remove-Item -Path $outputDir -Recurse -Force
}

New-Item -ItemType Directory -Path $appDir | Out-Null
New-Item -ItemType Directory -Path $dataDir | Out-Null
New-Item -ItemType Directory -Path $configDir | Out-Null

Copy-Item -Path "dist\heritage_backend\*" -Destination $appDir -Recurse -Force
if (Test-Path "static") { Copy-Item -Path "static" -Destination $appDir -Recurse -Force }
if (Test-Path "templates") { Copy-Item -Path "templates" -Destination $appDir -Recurse -Force }
if (Test-Path ".env.example") { Copy-Item -Path ".env.example" -Destination $configDir -Force }

Write-Host "[desktop-runtime] Runtime is ready: $outputDir (app/data/config)"
Write-Host "[desktop-runtime] Next: cd frontend ; npm run desktop:pack"
