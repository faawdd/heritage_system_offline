from pathlib import Path
from itertools import tee
from collections.abc import Mapping
import re

from django.db import DEFAULT_DB_ALIAS
from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.operations import DatabaseOperations as SQLiteDatabaseOperations

from heritage_system.sqlcipher.connection import connect_sqlcipher_database


FORMAT_QMARK_REGEX = re.compile(r'(?<!%)%s')


class SqlCipherCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        if params is None:
            return self.cursor.execute(query)
        param_names = list(params) if isinstance(params, Mapping) else None
        query = self._convert_query(query, param_names=param_names)
        return self.cursor.execute(query, params)

    def executemany(self, query, param_list):
        peekable, param_list = tee(iter(param_list))
        if (params := next(peekable, None)) and isinstance(params, Mapping):
            param_names = list(params)
        else:
            param_names = None
        query = self._convert_query(query, param_names=param_names)
        return self.cursor.executemany(query, param_list)

    def _convert_query(self, query, *, param_names=None):
        if param_names is None:
            return FORMAT_QMARK_REGEX.sub('?', query).replace('%%', '%')
        return query % {name: f':{name}' for name in param_names}

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class SqlCipherDatabaseFeatures:
    def __init__(self, wrapped_features):
        self._wrapped_features = wrapped_features

    @property
    def max_query_params(self):
        return 999

    def __getattr__(self, name):
        return getattr(self._wrapped_features, name)


class SqlCipherDatabaseOperations(SQLiteDatabaseOperations):
    """兼容 sqlcipher3 的 DatabaseOperations。

    sqlcipher3 的连接对象是 C 扩展类型（不可 monkeypatch），缺少标准库
    sqlite3.Connection 才有的 ``getlimit()``。Django 6.1 起
    ``_quote_params_for_last_executed_query()`` 会调用
    ``connection.getlimit(SQLITE_LIMIT_COLUMN)``，在 sqlcipher 后端下抛
    ``AttributeError``；由于该路径位于 DEBUG 的 SQL 日志包装器中，会让
    桌面版首次建库（``migrate``）在第一条带参数的 INSERT 上直接崩溃。

    这里退回按 SQLite 默认上限分批的实现（与 Django 5.x 行为一致），
    使同一份后端在 Django 5.x / 6.x 下都可用。
    """

    # SQLITE_LIMIT_VARIABLE_NUMBER 默认值，与 SqlCipherDatabaseFeatures.max_query_params 一致。
    _QUOTE_PARAMS_BATCH_SIZE = 999

    def _quote_params_for_last_executed_query(self, params):
        batch_size = self._QUOTE_PARAMS_BATCH_SIZE
        if len(params) > batch_size:
            results = ()
            for index in range(0, len(params), batch_size):
                chunk = params[index:index + batch_size]
                results += self._quote_params_for_last_executed_query(chunk)
            return results

        sql = 'SELECT ' + ', '.join(['QUOTE(?)'] * len(params))
        # 绕过 Django 的包装器直接使用底层连接，避免记录该查询造成无限递归。
        cursor = self.connection.connection.cursor()
        try:
            return cursor.execute(sql, params).fetchone()
        finally:
            cursor.close()


class DatabaseWrapper(SQLiteDatabaseWrapper):
    vendor = 'sqlite'
    ops_class = SqlCipherDatabaseOperations

    def get_new_connection(self, conn_params):
        database_name = conn_params.get('database') or self.settings_dict.get('NAME')
        create_if_missing = not Path(str(database_name)).exists()
        return connect_sqlcipher_database(database_name, create_if_missing=create_if_missing, verify=True)

    def create_cursor(self, name=None):
        return SqlCipherCursorWrapper(self.connection.cursor())

    def __init__(self, settings_dict, alias=DEFAULT_DB_ALIAS):
        super().__init__(settings_dict, alias)
        self.features = SqlCipherDatabaseFeatures(self.features)
