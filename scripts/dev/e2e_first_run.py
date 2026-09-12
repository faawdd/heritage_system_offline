"""端到端演练：模拟全新安装的首次启动（建库 + 迁移 + 超级管理员初始化）。"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
work_root = Path(tempfile.mkdtemp(prefix='heritage-e2e-'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'heritage_system.settings'
os.environ['HERITAGE_DESKTOP_MODE'] = '1'
os.environ['DJANGO_DEBUG'] = '1'
os.environ['DJANGO_FORCE_HTTPS'] = '0'
os.environ['HERITAGE_APP_DIR'] = str(repo_root)
os.environ['HERITAGE_DATA_DIR'] = str(work_root / 'data')
os.environ['HERITAGE_CONFIG_DIR'] = str(work_root / 'config')
os.environ['HERITAGE_LOG_DIR'] = str(work_root / 'logs')
os.environ['HERITAGE_UPLOAD_DIR'] = str(work_root / 'uploads')
os.environ['HERITAGE_BACKUP_DIR'] = str(work_root / 'backup')
os.environ['HERITAGE_DB_FILE'] = str(work_root / 'data' / 'database.db')
os.environ['HERITAGE_BOOTSTRAP_ADMIN_PASSWORD'] = 'WizardPass#2026'

sys.path.insert(0, str(repo_root))

import django

django.setup()

from heritage_system.sqlcipher.maintenance import bootstrap_sqlcipher_database

result = bootstrap_sqlcipher_database()
print('bootstrap result:', result)

db_path = Path(os.environ['HERITAGE_DB_FILE'])
key_path = work_root / 'config' / 'key.bin'
print('db exists      :', db_path.exists(), db_path.stat().st_size if db_path.exists() else 0)
print('key exists     :', key_path.exists())

# 确认是真正的加密库：文件头不应是 "SQLite format 3"
head = db_path.read_bytes()[:16]
print('db header      :', head[:6])
print('IS ENCRYPTED   :', head != b'SQLite format 3\x00')

from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.filter(username='admin').first()
print('admin exists   :', u is not None)
print('admin superuser:', bool(u and u.is_superuser))
print('admin groups   :', list(u.groups.values_list('name', flat=True)) if u else [])
print('wizard password verifies:', bool(u and u.check_password('WizardPass#2026')))
print('test/test verifies      :', bool(u and u.check_password('test')))

# 用错误 key 打开必须失败
import sqlcipher3

conn = sqlcipher3.connect(str(db_path))
try:
    conn.execute("PRAGMA key = 'wrong-key'")
    conn.execute('SELECT count(*) FROM django_migrations').fetchall()
    print('WRONG-KEY READ : UNEXPECTEDLY SUCCEEDED')
except Exception as exc:
    print('WRONG-KEY READ : rejected ->', type(exc).__name__)
conn.close()

shutil.rmtree(work_root, ignore_errors=True)
print('E2E_DONE')
