from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3

from .dbapi import resolve_sqlcipher_dbapi
from .key_store import SqlCipherKeyError, load_database_key
from .paths import get_config_dir


class SqlCipherDatabaseError(RuntimeError):
    pass


def _desktop_mode_enabled() -> bool:
    return str(os.environ.get('HERITAGE_DESKTOP_MODE') or '').lower() in {'1', 'true', 'yes', 'on'}


def _should_fallback_without_key(error: Exception, database_path: Path) -> bool:
    if not _desktop_mode_enabled():
        return False
    if not database_path.exists():
        return False
    message = str(error or '')
    return 'SQLCipher key file not found' in message


def _open_plain_sqlite(database_path: Path, verify: bool):
    connection = sqlite3.connect(str(database_path))
    try:
        if verify:
            verify_connection(connection)
    except Exception:
        connection.close()
        raise
    return connection


def _quote_sqlcipher_value(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def apply_database_key(connection, key_text: str) -> None:
    connection.execute(f"PRAGMA key = {_quote_sqlcipher_value(key_text)}")
    connection.execute('PRAGMA foreign_keys = ON')


def verify_connection(connection) -> None:
    cursor = connection.execute('PRAGMA integrity_check;')
    rows = cursor.fetchall()
    values = [row[0] if isinstance(row, tuple) else row[0] for row in rows]
    if values != ['ok']:
        raise SqlCipherDatabaseError(f'Database integrity check failed: {values!r}')


def connect_sqlcipher_database(database_path: str | Path, create_if_missing: bool = False, verify: bool = True):
    dbapi = resolve_sqlcipher_dbapi()
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = dbapi.connect(str(path))
    try:
        if getattr(dbapi, '__name__', '') != 'sqlite3':
            key_text = load_database_key(get_config_dir(), create_if_missing=create_if_missing)
            apply_database_key(connection, key_text)
        if verify:
            verify_connection(connection)
    except SqlCipherKeyError as exc:
        connection.close()
        if _should_fallback_without_key(exc, path):
            return _open_plain_sqlite(path, verify=verify)
        raise
    except Exception:
        connection.close()
        raise
    return connection


@contextmanager
def sqlcipher_connection(database_path: str | Path, create_if_missing: bool = False, verify: bool = True):
    connection = connect_sqlcipher_database(database_path, create_if_missing=create_if_missing, verify=verify)
    try:
        yield connection
    finally:
        connection.close()
