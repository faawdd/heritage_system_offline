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

$pyVersionText = (& $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
$parts = $pyVersionText.Trim().Split('.')
$major = [int]$parts[0]
$minor = [int]$parts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    throw "[desktop-runtime] ERROR: $pythonExe is Python $pyVersionText, but Python >= 3.10 is required (Django>=5)."
}

Write-Host "[desktop-runtime] Using Python: $pythonExe (version $pyVersionText)"

Write-Host "[desktop-runtime] Installing build tools..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt
& $pythonExe -m pip install -r requirements-sqlcipher.txt
& $pythonExe -m pip install pyinstaller

Write-Host "[desktop-runtime] Building backend executable..."
& $pythonExe -m PyInstaller `
    desktop_backend.py `
    --name heritage_backend `
    --noconfirm `
    --clean `
    --collect-data rasterio `
    --hidden-import sqlite3 `
    --hidden-import heritage_system.db.backends.sqlcipher `
    --hidden-import heritage_system.db.backends.sqlcipher.base `
    --collect-all sqlcipher3 `
    --collect-all cryptography `
    --collect-all keyring `
    --onedir

$outputDir = Join-Path $projectRoot $OutputRoot
$appDir = Join-Path $outputDir "app"
$dataDir = Join-Path $outputDir "data"
$configDir = Join-Path $outputDir "config"

$frontendIndex = Join-Path $projectRoot "static\frontend\index.html"
if (-not (Test-Path $frontendIndex)) {
    throw "[desktop-runtime] ERROR: Missing frontend bundle at static/frontend/index.html. Run: cd frontend ; npm run build"
}

if ($env:SKIP_TDT_PREFETCH -ne "1") {
    Write-Host "[desktop-runtime] Prefetch TianDiTu offline tiles for Turpan..."
    & $pythonExe "$projectRoot\scripts\prefetch_tianditu_tiles.py" --output-dir "$projectRoot\static\tiles\tianditu"
} else {
    Write-Host "[desktop-runtime] SKIP_TDT_PREFETCH=1, skip TianDiTu tile prefetch"
}

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
