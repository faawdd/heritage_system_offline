"""验证开发模式（Vite dev server）能否正确代理后端资源。

同时启动 Django runserver 与 Vite，然后通过 Vite 端口访问：
  - /static/tiles/**  离线天地图瓦片（本次新增的代理规则）
  - /api/**           后端 API（原有代理规则）
以此确认前端热更新开发时可以调试离线底图。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

repo_root = Path(__file__).resolve().parents[2]
frontend = repo_root / 'frontend'
work_root = repo_root / '.smoke-runtime'
django_port = 8732
vite_port = 5177
vite_base = f'http://127.0.0.1:{vite_port}'
django_base = f'http://127.0.0.1:{django_port}'
password = 'SmokeTest#2026'

node_dir = Path(os.environ['APPDATA']) / 'fnm' / 'node-versions' / 'v24.21.0' / 'installation'
env = dict(os.environ)
env.update({
    'DJANGO_SETTINGS_MODULE': 'heritage_system.settings',
    'HERITAGE_DESKTOP_MODE': '1',
    'DJANGO_DEBUG': '1',
    'DJANGO_FORCE_HTTPS': '0',
    'HERITAGE_APP_DIR': str(repo_root),
    'HERITAGE_DATA_DIR': str(work_root / 'data'),
    'HERITAGE_CONFIG_DIR': str(work_root / 'config'),
    'HERITAGE_LOG_DIR': str(work_root / 'logs'),
    'HERITAGE_UPLOAD_DIR': str(work_root / 'uploads'),
    'HERITAGE_BACKUP_DIR': str(work_root / 'backup'),
    'HERITAGE_DB_FILE': str(work_root / 'data' / 'database.db'),
    'HERITAGE_BOOTSTRAP_ADMIN_PASSWORD': password,
    'HERITAGE_DESKTOP_BACKEND_PORT': str(django_port),
    'PATH': f"{node_dir};{env.get('PATH', '')}",
})

if work_root.exists():
    shutil.rmtree(work_root, ignore_errors=True)
work_root.mkdir(parents=True, exist_ok=True)

py = str(repo_root / '.venv' / 'Scripts' / 'python.exe')
subprocess.run([py, 'manage.py', 'sqlcipher_bootstrap'], cwd=str(repo_root), env=env,
               capture_output=True, text=True, check=True)

django_proc = subprocess.Popen(
    [py, 'manage.py', 'runserver', f'127.0.0.1:{django_port}', '--noreload'],
    cwd=str(repo_root), env=env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
vite_proc = subprocess.Popen(
    [str(node_dir / 'node.exe'), str(frontend / 'node_modules' / 'vite' / 'bin' / 'vite.js'),
     '--port', str(vite_port), '--strictPort', '--host', '127.0.0.1'],
    cwd=str(frontend), env=env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

results = []
try:
    def wait_up(url, tries=80):
        for _ in range(tries):
            try:
                requests.get(url, timeout=2)
                return True
            except Exception:
                time.sleep(0.5)
        return False

    print('== wait for backends ==')
    print('   django up:', wait_up(django_base + '/api/system-version/'))
    print('   vite   up:', wait_up(vite_base + '/static/frontend/'))

    def check(name, cond, extra=''):
        results.append((name, bool(cond), extra))
        print(f"   {'PASS' if cond else 'FAIL'}  {name} {extra}")

    print('== through Vite dev server (hot-reload workflow) ==')
    r = requests.get(vite_base + '/static/frontend/', timeout=20)
    check('vite serves app entry', r.status_code == 200 and '<div id="app">' in r.text,
          f'[status={r.status_code}]')

    tile = None
    tile_root = repo_root / 'static' / 'tiles' / 'tianditu'
    for p in tile_root.rglob('*.png'):
        tile = p.relative_to(repo_root / 'static').as_posix()
        break
    if tile:
        r = requests.get(f'{vite_base}/static/{tile}', timeout=25)
        ok = r.status_code == 200 and (r.content[:2] == b'\xff\xd8' or r.content[:3] == b'\x89PN')
        check('vite proxies /static/tiles -> Django', ok, f'[/static/{tile} status={r.status_code}]')
    else:
        check('tile file exists', False)

    r = requests.post(vite_base + '/api/v1/system/login/',
                      json={'username': 'admin', 'password': password}, timeout=25)
    ok = r.status_code == 200
    access = ''
    if ok:
        access = (r.json().get('data') or {}).get('access_token', '')
        ok = bool(access)
    check('vite proxies /api -> Django (JWT login)', ok, f'[status={r.status_code}]')

    r = requests.get(vite_base + '/api/v1/system/profile/',
                     headers={'Authorization': f'Bearer {access}'} if access else {}, timeout=25)
    check('vite-proxied authed API works', r.status_code == 200, f'[status={r.status_code}]')
finally:
    for proc in (vite_proc, django_proc):
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()

passed = sum(1 for _, ok, _ in results if ok)
print(f'\nDEV-SMOKE SUMMARY: {passed}/{len(results)} passed')
for name, ok, extra in results:
    if not ok:
        print('  FAILED:', name, extra)
print('DEV_SMOKE_DONE' if passed == len(results) else 'DEV_SMOKE_HAS_FAILURES')
