"""验证 v1.2.12 新增的项目管理端点在离线 JWT 鉴权下可用（不抛 403）。

在线版把这些端点直接指向带 @staff_member_required 的 legacy 视图（仅 session 认证），
离线版必须经 DRF 包装类（_call_legacy_view 剥装饰器 + IsManagementAdmin），
否则 Vue 端带 JWT 访问会全线 403。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

repo_root = Path(__file__).resolve().parents[2]
work_root = repo_root / '.smoke-projects'
port = int(os.environ.get('PROJ_PORT', '8736'))
base = f'http://127.0.0.1:{port}'
password = 'ProjTest#2026'

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
    'HERITAGE_BOOTSTRAP_ADMIN_PASSWORD': password,
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
    subprocess.run([py, 'manage.py', 'sqlcipher_bootstrap'], cwd=str(repo_root),
                   env=env, capture_output=True, text=True, check=True)
    proc = subprocess.Popen([py, 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'],
                            cwd=str(repo_root), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            requests.get(base + '/api/v1/health/', timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise SystemExit('server did not start')

    r = requests.post(base + '/api/v1/system/login/',
                      json={'username': 'admin', 'password': password}, timeout=25)
    access = (r.json().get('data') or {}).get('access_token', '') if r.status_code == 200 else ''
    check('login ok', bool(access))
    hdr = {'Authorization': f'Bearer {access}'}

    # 建一个项目，供后续端点使用
    # 注意：land_project_create_api 返回顶层 {'success', 'project_id', 'status'}，
    # 不是嵌套在 data 里。
    r = requests.post(base + '/api/v1/projects/create/',
                      json={'project_name': 'JWT 包装验证项目', 'company_name': '测试单位'},
                      headers=hdr, timeout=30)
    pid = ''
    body = {}
    try:
        body = r.json() if r.content else {}
    except ValueError:
        body = {}
    pid = body.get('project_id') or (body.get('data') or {}).get('id') or ''
    check('POST projects/create/ via JWT', r.status_code == 200 and body.get('success'),
          f'[status={r.status_code} body={str(body)[:120]}]')

    if not pid:
        # 回退：从列表里取一个
        lr = requests.get(base + '/api/v1/projects/', headers=hdr, timeout=30)
        rows = []
        if lr.status_code == 200:
            data = lr.json().get('data')
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get('rows') or data.get('items') or []
        if rows:
            pid = rows[0].get('id', '')
    # pid 为空时后续断言会全部退化成 404 假阳性，因此这里必须硬失败
    check('got project id', bool(pid), f'[pid={pid}]')
    if not pid:
        raise SystemExit('ABORT: 未取得 project_id，端点断言无意义')

    # v1.2.12 新增端点：鉴权层必须放行（不得 401/403）。
    # 404 需要区分：Django 路由未注册会返回 HTML 404；业务层 404 返回 JSON。
    endpoints = [
        ('GET', f'/api/v1/projects/{pid}/documents/archive/'),
        ('GET', f'/api/v1/projects/{pid}/controls/'),
        ('GET', f'/api/v1/projects/{pid}/'),
        ('POST', f'/api/v1/projects/{pid}/link-kml-record/'),
        ('POST', f'/api/v1/projects/{pid}/documents/generate/'),
        ('GET', '/api/v1/system/data-sync/options/'),
        ('GET', '/api/v1/system/sipu-boundary-import/status/00000000-0000-0000-0000-000000000000/'),
    ]
    for method, path in endpoints:
        try:
            resp = requests.request(method, base + path, headers=hdr, timeout=40,
                                    json={} if method == 'POST' else None)
            status = resp.status_code
            ctype = resp.headers.get('content-type', '')
        except Exception as exc:
            status = f'ERR {type(exc).__name__}'
            ctype = ''
        # 403 = 包装类缺失、被 @staff_member_required 拦下；401 = 未认证
        authed_through = status not in (401, 403) and not str(status).startswith('ERR')
        # 若为 404，必须是业务层 JSON 404，而不是 Django 路由未注册（HTML）
        route_registered = not (status == 404 and 'json' not in ctype.lower())
        check(f'{method} {path}', authed_through and route_registered,
              f'[status={status} ctype={ctype.split(";")[0]}]')

    # 匿名仍必须被拒（收紧后不得放行）
    r = requests.get(base + f'/api/v1/projects/{pid}/documents/archive/', timeout=25)
    check('anonymous archive -> 401', r.status_code == 401, f'[status={r.status_code}]')
finally:
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
    shutil.rmtree(work_root, ignore_errors=True)

passed = sum(1 for _, ok, _ in results if ok)
print(f'\nPROJECT-API SUMMARY: {passed}/{len(results)} passed')
for name, ok, extra in results:
    if not ok:
        print('  FAILED:', name, extra)
print('PROJECT_API_DONE' if passed == len(results) else 'PROJECT_API_HAS_FAILURES')
sys.exit(0 if passed == len(results) else 1)
