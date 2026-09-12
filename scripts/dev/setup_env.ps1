# Local dev/debug environment bootstrap.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\dev\setup_env.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\dev\setup_env.ps1 -NodeVersion 24.21.0
#
# Notes:
#   - Node is installed via fnm (keeps per-project version switching, no system-wide Node)
#   - Python deps go into the repo-local .venv (requires Python >= 3.10)
#   - CN mirrors are used so Electron / node binaries do not time out
#   - Keep this file ASCII-only: Windows PowerShell 5.1 reads .ps1 as ANSI when there is no BOM,
#     which is also the convention of the other scripts in this repo.
param(
    [string]$NodeVersion = "lts-latest",
    [switch]$SkipFrontend,
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $projectRoot

function Write-Step($msg) { Write-Host "[setup] $msg" -ForegroundColor Cyan }

# ---- 0. preflight ----
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python not found on PATH. Install Python 3.10+ first."
}
$pyVer = (& python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')")
Write-Step "python version: $pyVer"
if ([version]$pyVer -lt [version]'3.10') {
    throw "Django>=5 requires Python >= 3.10, got $pyVer."
}

# ---- 1. fnm / Node ----
$wingetFnm = Join-Path $env:LOCALAPPDATA `
    'Microsoft\WinGet\Packages\Schniz.fnm_Microsoft.Winget.Source_8wekyb3d8bbwe'
$fnmCmd = Get-Command fnm -ErrorAction SilentlyContinue
if (-not $fnmCmd) {
    # winget portable dir may not be on the current session PATH yet
    if (Test-Path (Join-Path $wingetFnm 'fnm.exe')) {
        $env:Path = "$wingetFnm;$env:Path"
        $fnmCmd = Get-Command fnm -ErrorAction SilentlyContinue
    }
}
if (-not $fnmCmd) {
    Write-Step "fnm not found, installing Schniz.fnm via winget ..."
    winget install -e --id Schniz.fnm --accept-package-agreements --accept-source-agreements --silent
    if (Test-Path (Join-Path $wingetFnm 'fnm.exe')) {
        $env:Path = "$wingetFnm;$env:Path"
        $fnmCmd = Get-Command fnm -ErrorAction SilentlyContinue
    }
    if (-not $fnmCmd) {
        throw "fnm still unavailable after install. Open a new terminal (PATH refresh) and retry."
    }
}
Write-Step "fnm version: $(& fnm --version)"

# CN mirror for node distributions
$env:FNM_NODE_DIST_MIRROR = 'https://npmmirror.com/mirrors/node'
Write-Step "ensuring node $NodeVersion is installed ..."
& fnm install $NodeVersion

# fnm exec cannot spawn npm.cmd directly, so resolve the install dir explicitly
& fnm use $NodeVersion 2>$null | Out-Null
$nodeExePath = (& fnm exec --using=$NodeVersion node -p "process.execPath") | Out-String
$nodeDir = Split-Path -Parent $nodeExePath.Trim()
$env:Path = "$nodeDir;$env:Path"
Write-Step "node: $(& node -v)  npm: $(& npm.cmd -v)"

function npmrcEnsure($key, $value) {
    $npmrc = Join-Path $env:USERPROFILE '.npmrc'
    $line = "$key=$value"
    $existing = @()
    if (Test-Path $npmrc) { $existing = @(Get-Content $npmrc) }
    if (@($existing | Where-Object { $_ -like "$key=*" }).Count -eq 0) {
        Write-Output $line | Out-File -FilePath $npmrc -Append -Encoding ascii
        Write-Step "  appended ~/.npmrc : $key"
    }
}

Write-Step "configuring npm / Electron mirrors (user scope) ..."
& npm.cmd config set registry https://registry.npmmirror.com --location=user | Out-Null
npmrcEnsure 'electron_mirror' 'https://npmmirror.com/mirrors/electron/'
npmrcEnsure 'electron_builder_binaries_mirror' 'https://npmmirror.com/mirrors/electron-builder-binaries/'

# ---- 2. frontend deps ----
if (-not $SkipFrontend) {
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        Write-Step "installing frontend deps (npm ci) ..."
        $env:ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/'
        $env:ELECTRON_BUILDER_BINARIES_MIRROR = 'https://npmmirror.com/mirrors/electron-builder-binaries/'
        & npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
        if (-not (Test-Path 'node_modules\electron\dist\electron.exe')) {
            throw "Electron binary missing; check mirror reachability and rerun npm ci"
        }
        Write-Step "Electron binary ready"
    }
    finally { Pop-Location }
}

# ---- 3. python venv + deps ----
if (-not $SkipPython) {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        Write-Step "creating virtualenv .venv ..."
        & python -m venv .venv
    }
    $py = Join-Path $projectRoot '.venv\Scripts\python.exe'
    Write-Step "upgrading pip / setuptools / wheel ..."
    & $py -m pip install --upgrade pip setuptools wheel
    Write-Step "installing requirements.txt ..."
    & $py -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "requirements.txt install failed" }
    Write-Step "installing requirements-sqlcipher.txt ..."
    & $py -m pip install -r requirements-sqlcipher.txt
    if ($LASTEXITCODE -ne 0) { throw "requirements-sqlcipher.txt install failed" }
}

# ---- 4. self check ----
$py = Join-Path $projectRoot '.venv\Scripts\python.exe'
Write-Step "running env self-check ..."
& $py (Join-Path $projectRoot 'scripts\dev\verify_python_env.py')
if ($LASTEXITCODE -ne 0) { throw "python env self-check failed" }

Write-Host ""
Write-Host "Environment ready. Typical next steps:" -ForegroundColor Green
Write-Host "  1) copy config    : Copy-Item .env.example .env"
Write-Host "  2) first-run DB   : .venv\Scripts\python.exe manage.py sqlcipher_bootstrap"
Write-Host "  3) backend        : .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000"
Write-Host "  4) frontend HMR   : cd frontend ; npm run dev   (Vite proxies /api and /static/tiles)"
Write-Host "  5) desktop debug  : powershell -File scripts\start_offline.ps1 -Mode desktop"
Write-Host "  6) smoke checks   : .venv\Scripts\python.exe scripts\dev\smoke_http.py"
