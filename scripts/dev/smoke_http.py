"""本地开发/调试环境冒烟测试：真实启动后端并用 HTTP 验证关键离线链路。

覆盖：
  1. SPA history fallback（/login、/dashboard 直接访问不应 404）
  2. 离线天地图瓦片可访问（v1.2.11 特性）
  3. 前端 bundle 入口可访问
  4. JWT 登录端点返回 access/refresh
  5. 受保护 API 在无 token 时被拒绝
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

repo_root = Path(__file__).resolve().parents[2]
work_root = Path(os.environ.get('SMOKE_WORK_DIR', repo_root / '.smoke-runtime'))
port = int(os.environ.get('SMOKE_PORT', '8731'))
base = f'http://127.0.0.1:{port}'
password = 'SmokeTest#2026'

env = dict(os.environ)
env.update({
    'DJANGO_SETTINGS_MODULE': 'heritage_system.settings',
    'HERITAGE_DESKTOP_MODE': '1',
    'DJANGO_DEBUG': '1',
    'DJANGO_FORCE_HTTPS': '0',
    'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1',
    'HERITAGE_APP_DIR': str(repo_root),
    'HERITAGE_DATA_DIR': str(work_root / 'data'),
    'HERITAGE_CONFIG_DIR': str(work_root / 'config'),
    'HERITAGE_LOG_DIR': str(work_root / 'logs'),
    'HERITAGE_UPLOAD_DIR': str(work_root / 'uploads'),
    'HERITAGE_BACKUP_DIR': str(work_root / 'backup'),
    'HERITAGE_DB_FILE': str(work_root / 'data' / 'database.db'),
    'HERITAGE_BOOTSTRAP_ADMIN_PASSWORD': password,
})

if work_root.exists():
    shutil.rmtree(work_root, ignore_errors=True)
work_root.mkdir(parents=True, exist_ok=True)

print('== 1. bootstrap encrypted database ==')
boot = subprocess.run(
    [str(repo_root / '.venv' / 'Scripts' / 'python.exe'), 'manage.py', 'sqlcipher_bootstrap'],
    cwd=str(repo_root), env=env, capture_output=True, text=True,
)
print('   exit code:', boot.returncode)
if boot.returncode != 0:
    print(boot.stdout[-2000:])
    print(boot.stderr[-3000:])
    raise SystemExit('bootstrap failed')

server = subprocess.Popen(
    [str(repo_root / '.venv' / 'Scripts' / 'python.exe'), 'manage.py', 'runserver',
     f'127.0.0.1:{port}', '--noreload'],
    cwd=str(repo_root), env=env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

results = []
try:
    print('== 2. wait for server ==')
    for _ in range(60):
        try:
            requests.get(base + '/api/system-version/', timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise SystemExit('server did not come up')
    print('   server up on', base)

    def check(name, cond, extra=''):
        results.append((name, bool(cond), extra))
        print(f"   {'PASS' if cond else 'FAIL'}  {name} {extra}")

    print('== 3. SPA history fallback (v1.2.11 fix) ==')
    for route in ('/login', '/dashboard', '/heritage/map'):
        r = requests.get(base + route, timeout=10)
        check(f'SPA fallback {route}', r.status_code == 200 and '<div id="app">' in r.text,
              f'[status={r.status_code}]')

    print('== 4. offline tiles + frontend bundle ==')
    r = requests.get(base + '/static/frontend/index.html', timeout=10)
    check('static/frontend/index.html served', r.status_code in (200, 302), f'[status={r.status_code}]')

    tile_root = repo_root / 'static' / 'tiles' / 'tianditu'
    tile_file = None
    if tile_root.exists():
        for p in tile_root.rglob('*.png'):
            tile_file = p
            break
    if tile_file:
        rel = tile_file.relative_to(repo_root / 'static').as_posix()
        r = requests.get(f'{base}/static/{rel}', timeout=15)
        # 天地图 img 层即使以 .png 命名，内容也可能是 JPEG；两者都算有效瓦片。
        is_image = r.content[:3] == b'\x89PN' or r.content[:2] == b'\xff\xd8'
        check('offline Tianditu tile', r.status_code == 200 and is_image,
              f'[/static/{rel} status={r.status_code} bytes={len(r.content)}]')
    else:
        check('offline Tianditu tile present on disk', False, '[no tile files under static/tiles/tianditu]')

    print('== 5. JWT auth chain ==')
    r = requests.post(base + '/api/v1/system/login/',
                      json={'username': 'admin', 'password': password}, timeout=15)
    ok = r.status_code == 200
    access = ''
    if ok:
        try:
            payload = r.json()
            data = payload.get('data') or {}
            access = data.get('access_token') or payload.get('access') or ''
            ok = bool(access)
        except Exception:
            ok = False
    check('login returns JWT access token', ok, f'[status={r.status_code}]')

    r2 = requests.post(base + '/api/v1/system/login/',
                       json={'username': 'admin', 'password': 'test'}, timeout=15)
    check('wrong password rejected', r2.status_code == 401, f'[status={r2.status_code}]')

    r = requests.get(base + '/api/v1/system/users/', timeout=15)
    check('protected API without token is rejected', r.status_code in (401, 403),
          f'[status={r.status_code}]')

    if access:
        r = requests.get(base + '/api/v1/system/users/',
                         headers={'Authorization': f'Bearer {access}'}, timeout=20)
        check('protected API with JWT works', r.status_code == 200, f'[status={r.status_code}]')

    print('== 6. Django admin entry ==')
    r = requests.get(base + '/admin/login/', timeout=15)
    check('/admin/login/ reachable', r.status_code in (200, 302), f'[status={r.status_code}]')

    # 探针（不计入通过/失败）：core/permissions/api_permissions.py 在 DEBUG + localhost 时
    # 会放行 IsManagementAdmin。桌面版 desktop_backend.py 硬编码 DJANGO_DEBUG=1，
    # 因此本地任意进程可无 token 访问管理类接口 —— 记录为已知风险，供后续收紧。
    r = requests.get(base + '/api/v1/projects/', timeout=20)
    print(f'   PROBE  IsManagementAdmin endpoint without token -> status={r.status_code} '
          f'({"BYPASS ACTIVE" if r.status_code == 200 else "denied"})')
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except Exception:
        server.kill()

passed = sum(1 for _, ok, _ in results if ok)
print(f'\nSMOKE SUMMARY: {passed}/{len(results)} passed')
for name, ok, extra in results:
    if not ok:
        print('  FAILED:', name, extra)
print('SMOKE_DONE' if passed == len(results) else 'SMOKE_HAS_FAILURES')
