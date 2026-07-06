from pathlib import Path

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper

from heritage_system.sqlcipher.connection import connect_sqlcipher_database


class DatabaseWrapper(SQLiteDatabaseWrapper):
    vendor = 'sqlite'

    def get_new_connection(self, conn_params):
        database_name = conn_params.get('database') or self.settings_dict.get('NAME')
        create_if_missing = not Path(str(database_name)).exists()
        return connect_sqlcipher_database(database_name, create_if_missing=create_if_missing, verify=True)
