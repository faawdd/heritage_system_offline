import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')

import sqlcipher3
import rasterio
import pyproj
import pandas
import docxtpl
import keyring
import cryptography
import django
from django.db.backends.sqlite3.base import DatabaseWrapper as _sw  # noqa

print('python      :', sys.version.split()[0])
print('django      :', django.get_version())
print('sqlcipher3  :', getattr(sqlcipher3, 'version', 'n/a'), '/ module=', sqlcipher3.__name__)
print('rasterio    :', rasterio.__version__)
print('pyproj      :', pyproj.__version__)
print('pandas      :', pandas.__version__)
print('cryptography:', cryptography.__version__)

# 关键：确认 sqlcipher3 真能加密/解密，而不是回退到明文 sqlite3
dbapi = None
from heritage_system.sqlcipher.dbapi import resolve_sqlcipher_dbapi
dbapi = resolve_sqlcipher_dbapi()
print('resolved dbapi module :', dbapi.__name__)

import tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp()) / 'enc_probe.db'
conn = dbapi.connect(str(tmp))
conn.execute("PRAGMA key = 'probe-key-123'")
conn.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)')
conn.execute("INSERT INTO t (v) VALUES ('secret')")
conn.commit()
conn.close()

# 不带 key 直接打开应失败（证明确实加密）
conn2 = dbapi.connect(str(tmp))
try:
    rows = conn2.execute('SELECT count(*) FROM t').fetchall()
    print('UNEXPECTED: readable without key ->', rows)
except Exception as exc:
    print('OK encrypted (no-key read rejected):', type(exc).__name__)
conn2.close()

conn3 = dbapi.connect(str(tmp))
conn3.execute("PRAGMA key = 'probe-key-123'")
print('OK with key, row =', conn3.execute('SELECT v FROM t').fetchone())
conn3.close()
print('ALL_PY_CHECKS_PASSED')
