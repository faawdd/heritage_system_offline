"""桌面登录链路回归：验证渲染进程改走的"真实后端 JWT 登录"整条链路可用。

对应本次修复的目标：
  1. 废除主进程假登录：test/test 不再能登录（后端本就没有该账号）。
  2. 打通真实 JWT：/api/v1/system/login/ 返回 access/refresh，
     令牌可访问已收紧权限的 IsManagementAdmin 接口，refresh 可续期。
  3. 向导一致性：用初始化向导设置的超级管理员密码可成功登录。

以桌面模式 + DEBUG=0 运行，模拟打包后的真实鉴权环境。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

repo_root = Path(__file__).resolve().parents[2]
work_root = repo_root / '.smoke-login'
port = int(os.environ.get('LOGIN_SMOKE_PORT', '8734'))
base = f'http://127.0.0.1:{port}'
# 模拟初始化向导为超级管理员 admin 设置的密码
wizard_password = 'Wizard#Pass2026'

py = str(repo_root / '.venv' / 'Scripts' / 'python.exe')

env = dict(os.environ)
env.update({
    'DJANGO_SETTINGS_MODULE': 'heritage_system.settings',
    'HERITAGE_DESKTOP_MODE': '1',
    'DJANGO_DEBUG': '0',
    'DJANGO_FORCE_HTTPS': '0',
    'HERITAGE_APP_DIR': str(repo_root),
    'HERITAGE_DATA_DIR': str(work_root / 'data'),
    'HERITAGE_CONFIG_DIR': str(work_root / 'config'),
    'HERITAGE_LOG_DIR': str(work_root / 'logs'),
    'HERITAGE_UPLOAD_DIR': str(work_root / 'uploads'),
    'HERITAGE_BACKUP_DIR': str(work_root / 'backup'),
    'HERITAGE_DB_FILE': str(work_root / 'data' / 'database.db'),
    'HERITAGE_BOOTSTRAP_ADMIN_PASSWORD': wizard_password,
})
env.pop('HERITAGE_DEV_ALLOW_LOCAL_BYPASS', None)

if work_root.exists():
    shutil.rmtree(work_root, ignore_errors=True)
work_root.mkdir(parents=True, exist_ok=True)

results = []


def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(f"   {'PASS' if cond else 'FAIL'}  {name} {extra}")


proc = None
try:
    print('== bootstrap (simulates first-run wizard) ==')
    boot = subprocess.run([py, 'manage.py', 'sqlcipher_bootstrap'], cwd=str(repo_root),
                          env=env, capture_output=True, text=True)
    check('sqlcipher_bootstrap ok', boot.returncode == 0,
          '' if boot.returncode == 0 else boot.stderr[-400:])

    proc = subprocess.Popen([py, 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'],
                            cwd=str(repo_root), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    up = False
    for _ in range(80):
        try:
            requests.get(base + '/api/v1/health/', timeout=2)
            up = True
            break
        except Exception:
            time.sleep(0.5)
    check('server up (DEBUG=0 desktop)', up)
    if not up:
        raise SystemExit('server did not start')

    print('== 1. wizard password logs in and issues JWT ==')
    r = requests.post(base + '/api/v1/system/login/',
                      json={'username': 'admin', 'password': wizard_password}, timeout=25)
    access = refresh = ''
    if r.status_code == 200:
        data = (r.json().get('data') or {})
        access = data.get('access_token', '')
        refresh = data.get('refresh_token', '')
    check('login(admin, wizard_password) -> 200', r.status_code == 200, f'[status={r.status_code}]')
    check('response carries access_token', bool(access))
    check('response carries refresh_token', bool(refresh))

    print('== 2. JWT unlocks a tightened IsManagementAdmin endpoint ==')
    r = requests.get(base + '/api/v1/system/version/',
                     headers={'Authorization': f'Bearer {access}'} if access else {}, timeout=25)
    check('authed management API -> 200', r.status_code == 200, f'[status={r.status_code}]')

    r = requests.get(base + '/api/v1/heritage/sites/',
                     headers={'Authorization': f'Bearer {access}'} if access else {}, timeout=25)
    check('authed heritage/sites -> 200', r.status_code == 200, f'[status={r.status_code}]')

    print('== 3. refresh token renews access ==')
    r = requests.post(base + '/api/v1/system/refresh/', json={'refresh': refresh}, timeout=25)
    new_access = ''
    if r.status_code == 200:
        new_access = (r.json().get('data') or {}).get('access', '')
    check('refresh -> new access token', bool(new_access), f'[status={r.status_code}]')
    if new_access:
        r = requests.get(base + '/api/v1/system/version/',
                         headers={'Authorization': f'Bearer {new_access}'}, timeout=25)
        check('refreshed token unlocks API -> 200', r.status_code == 200, f'[status={r.status_code}]')

    print('== 4. legacy test/test backdoor is gone ==')
    r = requests.post(base + '/api/v1/system/login/',
                      json={'username': 'test', 'password': 'test'}, timeout=25)
    check('login(test,test) rejected', r.status_code == 401, f'[status={r.status_code}]')
    r = requests.post(base + '/api/v1/system/login/',
                      json={'username': 'admin', 'password': 'test'}, timeout=25)
    check('login(admin,test) rejected', r.status_code == 401, f'[status={r.status_code}]')

    print('== 5. anonymous still denied (no bypass) ==')
    r = requests.get(base + '/api/v1/heritage/sites/', timeout=25)
    check('anonymous management API -> 401', r.status_code == 401, f'[status={r.status_code}]')
finally:
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
    shutil.rmtree(work_root, ignore_errors=True)

passed = sum(1 for _, ok, _ in results if ok)
print(f'\nDESKTOP-LOGIN SUMMARY: {passed}/{len(results)} passed')
for name, ok, extra in results:
    if not ok:
        print('  FAILED:', name, extra)
print('DESKTOP_LOGIN_DONE' if passed == len(results) else 'DESKTOP_LOGIN_HAS_FAILURES')
sys.exit(0 if passed == len(results) else 1)
