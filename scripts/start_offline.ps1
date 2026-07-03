param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$InitDeps,
    [string]$SuperAdminUsername = "",
    [string]$SuperAdminPassword = "",
    [switch]$SuperAdminCreateIfMissing
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

Write-Host "[offline] Ensuring debug super admin account (test/test)..."
& $pythonExe manage.py shell -c "from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group, Permission; ROLE_SUPER_ADMIN='超级管理员'; ROLE_ADMIN='管理员'; User=get_user_model(); super_group,_=Group.objects.get_or_create(name=ROLE_SUPER_ADMIN); admin_group,_=Group.objects.get_or_create(name=ROLE_ADMIN); super_group.permissions.set(Permission.objects.all()); admin_group.permissions.set(Permission.objects.exclude(content_type__app_label__in=['auth','contenttypes','sessions','admin'])); user,created=User.objects.get_or_create(username='test', defaults={'is_staff':True,'is_superuser':True,'is_active':True,'first_name':'调试账号'}); user.is_staff=True; user.is_superuser=True; user.is_active=True; user.set_password('test'); user.save(); user.groups.add(super_group); print('debug user ensured: test')"

if ($SuperAdminPassword) {
    if (-not $SuperAdminUsername) {
        $SuperAdminUsername = "admin"
    }
    Write-Host "[offline] Resetting super admin password for $SuperAdminUsername..."
    $resetArgs = @("manage.py", "reset_super_admin_password", "--username", $SuperAdminUsername, "--password", $SuperAdminPassword)
    if ($SuperAdminCreateIfMissing) {
        $resetArgs += "--create-if-missing"
    }
    & $pythonExe @resetArgs
}

$url = "http://${BindHost}:${Port}/"
Write-Host "[offline] Opening browser: $url"
Start-Process $url | Out-Null

Write-Host "[offline] Starting Django server at ${BindHost}:${Port}"
& $pythonExe manage.py runserver "${BindHost}:${Port}"
