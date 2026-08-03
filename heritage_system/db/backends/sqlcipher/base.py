from pathlib import Path
from itertools import tee
from collections.abc import Mapping
import re

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper

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


class DatabaseWrapper(SQLiteDatabaseWrapper):
    vendor = 'sqlite'

    def get_new_connection(self, conn_params):
        database_name = conn_params.get('database') or self.settings_dict.get('NAME')
        create_if_missing = not Path(str(database_name)).exists()
        return connect_sqlcipher_database(database_name, create_if_missing=create_if_missing, verify=True)

    def create_cursor(self, name=None):
        return SqlCipherCursorWrapper(self.connection.cursor())
