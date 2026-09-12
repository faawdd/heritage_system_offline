"""回归测试：离线桌面模式的鉴权收紧与静态资源解耦是否成立。

覆盖三件事：
  A. 默认（DEBUG=1、未设 HERITAGE_DEV_ALLOW_LOCAL_BYPASS）时，
     IsManagementAdmin 管理的接口必须拒绝匿名本机请求（历史上会 200 放行）。
  B. 静态资源与离线瓦片在 DEBUG=0 的桌面模式下仍可访问
     （证明已不再依赖 django.conf.urls.static.static() 的 DEBUG 开关）。
  C. 显式设 HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1 时，本机匿名请求恢复放行
     （证明开发便利开关仍可用，只是改为显式 opt-in）。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

repo_root = Path(__file__).resolve().parents[2]
work_root = repo_root / '.probe-runtime'
port = int(os.environ.get('AUDIT_PORT', '8733'))
base = f'http://127.0.0.1:{port}'
password = 'ProbeTest#2026'

# 这些视图在 core/api/views.py 中声明 permission_classes = [IsManagementAdmin]；
# 前 5 个是历史上 DEBUG+localhost 绕过实测返回 200 的接口。
MANAGEMENT_ENDPOINTS = [
    '/api/v1/heritage/map-points/',
    '/api/v1/heritage/classification-stats/',
    '/api/v1/heritage/sites/',
    '/api/v1/heritage/immovable/',
    '/api/v1/system/version/',
    '/api/v1/dashboard/overview/',
    '/api/v1/projects/',
]

py = str(repo_root / '.venv' / 'Scripts' / 'python.exe')


def build_env(debug: str, bypass):
    env = dict(os.environ)
    env.update({
        'DJANGO_SETTINGS_MODULE': 'heritage_system.settings',
        'HERITAGE_DESKTOP_MODE': '1',
        'DJANGO_DEBUG': debug,
        'DJANGO_FORCE_HTTPS': '0',
        'HERITAGE_APP_DIR': str(repo_root),
        'HERITAGE_DATA_DIR': str(work_root / 'data'),
        'HERITAGE_CONFIG_DIR': str(work_root / 'config'),
        'HERITAGE_LOG_DIR': str(work_root / 'logs'),
        'HERITAGE_UPLOAD_DIR': str(work_root / 'uploads'),
        'HERITAGE_BACKUP_DIR': str(work_root / 'backup'),
        'HERITAGE_DB_FILE': str(work_root / 'data' / 'database.db'),
        'HERITAGE_BOOTSTRAP_ADMIN_PASSWORD': password,
    })
    if bypass is None:
        env.pop('HERITAGE_DEV_ALLOW_LOCAL_BYPASS', None)
    else:
        env['HERITAGE_DEV_ALLOW_LOCAL_BYPASS'] = bypass
    return env


def start_server(env):
    proc = subprocess.Popen([py, 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'],
                            cwd=str(repo_root), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            requests.get(base + '/api/v1/health/', timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise RuntimeError('server did not come up')


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except Exception:
        proc.kill()


results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(f"   {'PASS' if cond else 'FAIL'}  {name} {extra}")


if work_root.exists():
    shutil.rmtree(work_root, ignore_errors=True)
work_root.mkdir(parents=True, exist_ok=True)

try:
    subprocess.run([py, 'manage.py', 'sqlcipher_bootstrap'], cwd=str(repo_root),
                   env=build_env('1', None), capture_output=True, text=True, check=True)

    # ---- A. DEBUG=1 但未显式开启开关：匿名本机请求必须全部被拒 ----
    print('== A. DEBUG=1, bypass NOT set -> anonymous localhost must be denied ==')
    proc = start_server(build_env('1', None))
    try:
        for path in MANAGEMENT_ENDPOINTS:
            try:
                status = requests.get(base + path, timeout=25).status_code
            except Exception as exc:
                status = f'ERR {type(exc).__name__}'
            check(f'denied {path}', status in (401, 403), f'[status={status}]')
    finally:
        stop_server(proc)

    # ---- B. DEBUG=0：静态资源与瓦片仍可用（解耦验证）----
    print('== B. DEBUG=0 desktop mode -> static assets must still be served ==')
    proc = start_server(build_env('0', None))
    try:
        tile_root = repo_root / 'static' / 'tiles' / 'tianditu'
        tile = next((p.relative_to(repo_root / 'static').as_posix()
                     for p in tile_root.rglob('*.png')), None)
        if tile:
            r = requests.get(f'{base}/static/{tile}', timeout=25)
            is_img = r.content[:2] == b'\xff\xd8' or r.content[:3] == b'\x89PN'
            check('offline tile served with DEBUG=0', r.status_code == 200 and is_img,
                  f'[/static/{tile} status={r.status_code}]')
        else:
            check('offline tile file exists', False)

        r = requests.get(base + '/static/frontend/index.html', timeout=25)
        check('frontend bundle served with DEBUG=0', r.status_code == 200,
              f'[status={r.status_code}]')

        r = requests.get(base + '/login', timeout=25)
        check('SPA fallback works with DEBUG=0',
              r.status_code == 200 and '<div id="app">' in r.text, f'[status={r.status_code}]')

        r = requests.post(base + '/api/v1/system/login/',
                          json={'username': 'admin', 'password': password}, timeout=25)
        access = ''
        if r.status_code == 200:
            access = (r.json().get('data') or {}).get('access_token', '')
        check('JWT login works with DEBUG=0', bool(access), f'[status={r.status_code}]')

        if access:
            r = requests.get(base + '/api/v1/system/version/',
                             headers={'Authorization': f'Bearer {access}'}, timeout=25)
            check('authed management API works with DEBUG=0', r.status_code == 200,
                  f'[status={r.status_code}]')
    finally:
        stop_server(proc)

    # ---- C. 显式开关：恢复本机匿名放行（开发便利仍可用）----
    print('== C. DEBUG=1 + HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1 -> bypass restored ==')
    proc = start_server(build_env('1', '1'))
    try:
        r = requests.get(base + '/api/v1/system/version/', timeout=25)
        check('explicit opt-in bypass works', r.status_code == 200, f'[status={r.status_code}]')
    finally:
        stop_server(proc)
finally:
    shutil.rmtree(work_root, ignore_errors=True)

passed = sum(1 for _, ok, _ in results if ok)
print(f'\nAUDIT SUMMARY: {passed}/{len(results)} passed')
for name, ok, extra in results:
    if not ok:
        print('  FAILED:', name, extra)
print('AUDIT_DONE' if passed == len(results) else 'AUDIT_HAS_FAILURES')
sys.exit(0 if passed == len(results) else 1)

