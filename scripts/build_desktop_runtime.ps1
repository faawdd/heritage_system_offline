param(
    [string]$OutputRoot = "desktop_runtime"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$buildRoot = Join-Path $projectRoot ".desktop-build"
Set-Location $projectRoot

$pythonExe = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $pythonExe = ".venv\Scripts\python.exe"
}

& $pythonExe -m pip install -r requirements.txt -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Failed to install desktop runtime dependencies" }

if (-not (Test-Path "static\frontend\index.html")) {
    throw "Missing frontend bundle: static/frontend/index.html. Run npm --prefix frontend run build first."
}

$addStatic = "$(Join-Path $projectRoot 'static');static"
$addTemplates = "$(Join-Path $projectRoot 'templates');templates"
& $pythonExe -m PyInstaller `
    desktop_backend.py `
    --name heritage_backend `
    --noconfirm `
    --clean `
    --onedir `
    --distpath (Join-Path $buildRoot "dist") `
    --workpath (Join-Path $buildRoot "work") `
    --specpath (Join-Path $buildRoot "spec") `
    --add-data $addStatic `
    --add-data $addTemplates `
    --collect-all django `
    --collect-all rest_framework `
    --collect-all rest_framework_simplejwt `
    --collect-all import_export `
    --collect-all rasterio `
    --collect-all waitress `
    --collect-all whitenoise `
    --collect-submodules core `
    --collect-submodules system `
    --collect-submodules heritage_system
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$appDir = Join-Path $projectRoot "$OutputRoot\app"
New-Item -ItemType Directory -Path $appDir -Force | Out-Null
Copy-Item -Path (Join-Path $buildRoot "dist\heritage_backend\*") -Destination $appDir -Recurse -Force
Copy-Item -Path "static" -Destination $appDir -Recurse -Force
Copy-Item -Path "templates" -Destination $appDir -Recurse -Force
Write-Host "Desktop runtime ready: $appDir"