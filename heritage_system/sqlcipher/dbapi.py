import importlib
import os


SQLCIPHER_MODULE_CANDIDATES = (
    'sqlcipher3.dbapi2',
    'sqlcipher3',
    'pysqlcipher3.dbapi2',
    'pysqlcipher3',
)


def resolve_sqlcipher_dbapi():
    allow_fallback = str(os.environ.get('HERITAGE_SQLCIPHER_ALLOW_FALLBACK') or '').lower() in {'1', 'true', 'yes', 'on'}
    desktop_mode = str(os.environ.get('HERITAGE_DESKTOP_MODE') or '').lower() in {'1', 'true', 'yes', 'on'}
    allow_fallback = allow_fallback or desktop_mode

    for module_name in SQLCIPHER_MODULE_CANDIDATES:
        try:
            return importlib.import_module(module_name)
        except Exception:
            continue

    if allow_fallback:
        import sqlite3

        return sqlite3

    raise RuntimeError(
        'SQLCipher DB-API module is not available. Install sqlcipher3 or '
        'run in desktop mode with sqlite fallback enabled.'
    )
