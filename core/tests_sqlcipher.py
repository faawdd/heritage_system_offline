from contextlib import contextmanager
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from heritage_system.sqlcipher import connection as sqlcipher_connection_module
from heritage_system.sqlcipher import key_store, maintenance


class SqlCipherKeyStoreTests(SimpleTestCase):
    def test_generate_database_key_is_256_bit_hex(self):
        key_text = key_store.generate_database_key()

        self.assertEqual(len(key_text), 64)
        self.assertTrue(all(char in '0123456789abcdef' for char in key_text))

    def test_store_and_load_fallback_key_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)

            with patch.object(key_store, '_windows_dpapi_available', return_value=False), \
                 patch.object(key_store, '_store_keyring_password', return_value=False), \
                 patch.object(key_store, '_fallback_encrypt', return_value=b'encrypted-key-payload'), \
                 patch.object(key_store, '_fallback_decrypt', return_value='abc123'):
                stored_path = key_store.store_database_key('abc123', config_dir=config_dir)

                self.assertTrue(stored_path.exists())
                self.assertEqual(stored_path.read_bytes(), b'encrypted-key-payload')
                self.assertEqual(key_store.load_database_key(config_dir=config_dir), 'abc123')


class SqlCipherConnectionTests(SimpleTestCase):
    def test_connect_applies_key_and_verifies_integrity(self):
        class FakeCursor:
            def fetchall(self):
                return [('ok',)]

        class FakeConnection:
            def __init__(self):
                self.calls = []
                self.closed = False

            def execute(self, sql):
                self.calls.append(sql)
                return FakeCursor()

            def close(self):
                self.closed = True

        fake_connection = FakeConnection()

        class FakeDbApi:
            Row = tuple

            def connect(self, _path):
                return fake_connection

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'database.db'
            fake_dbapi = FakeDbApi()

            with patch.object(sqlcipher_connection_module, 'resolve_sqlcipher_dbapi', return_value=fake_dbapi), \
                 patch.object(sqlcipher_connection_module, 'load_database_key', return_value='secret-key'), \
                 patch.object(sqlcipher_connection_module, 'get_config_dir', return_value=Path(temp_dir)):
                connection = sqlcipher_connection_module.connect_sqlcipher_database(
                    db_path,
                    create_if_missing=True,
                    verify=True,
                )

        self.assertIs(connection, fake_connection)
        self.assertIn("PRAGMA key = 'secret-key'", fake_connection.calls)
        self.assertIn('PRAGMA integrity_check;', fake_connection.calls)
        self.assertFalse(fake_connection.closed)


class SqlCipherMaintenanceTests(SimpleTestCase):
    def test_backup_database_creates_encrypted_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            database_path = temp_path / 'database.db'
            backup_dir = temp_path / 'backup'
            database_path.write_bytes(b'encrypted-bytes')

            backup_path = maintenance.backup_database(database_path=database_path, backup_dir=backup_dir)

            self.assertIsNotNone(backup_path)
            self.assertTrue(backup_path.exists())
            self.assertEqual(backup_path.read_bytes(), b'encrypted-bytes')
            self.assertTrue(backup_path.name.startswith('database_'))
            self.assertTrue(backup_path.name.endswith('.db.enc'))

    def test_rotate_database_password_rekeys_and_updates_key_store(self):
        class FakeCursor:
            def fetchall(self):
                return [('ok',)]

        class FakeConnection:
            def __init__(self):
                self.calls = []

            def execute(self, sql):
                self.calls.append(sql)
                return FakeCursor()

            def close(self):
                pass

        fake_connection = FakeConnection()

        @contextmanager
        def fake_sqlcipher_connection(*_args, **_kwargs):
            yield fake_connection

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            database_path = temp_path / 'database.db'
            database_path.write_bytes(b'encrypted-bytes')

            with patch.object(maintenance, 'get_database_path', return_value=database_path), \
                 patch.object(maintenance, 'get_backup_dir', return_value=temp_path / 'backup'), \
                 patch.object(maintenance, 'get_config_dir', return_value=temp_path / 'config'), \
                 patch.object(maintenance, 'load_database_key', return_value='old-key'), \
                 patch.object(maintenance, 'generate_database_key', return_value='new-key'), \
                 patch.object(maintenance, 'store_database_key') as store_mock, \
                 patch.object(maintenance, 'backup_database', return_value=temp_path / 'backup' / 'database_20260703.db.enc') as backup_mock, \
                 patch.object(maintenance, 'verify_database_file') as verify_mock, \
                 patch.object(maintenance, 'sqlcipher_connection', fake_sqlcipher_connection):
                result = maintenance.rotate_database_password(database_path=database_path)

        self.assertEqual(result['database_path'], str(database_path))
        self.assertEqual(result['backup_path'], str(temp_path / 'backup' / 'database_20260703.db.enc'))
        self.assertIn("PRAGMA rekey = 'new-key'", fake_connection.calls)
        store_mock.assert_called_once_with('new-key', temp_path / 'config')
        backup_mock.assert_called_once()
        verify_mock.assert_called()

    def test_bootstrap_database_invokes_migration_and_super_admin_setup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            database_path = temp_path / 'database.db'
            database_path.write_bytes(b'encrypted-bytes')

            with patch.object(maintenance, 'ensure_runtime_directories') as runtime_mock, \
                 patch.object(maintenance, 'get_database_path', return_value=database_path), \
                 patch.object(maintenance, 'get_backup_dir', return_value=temp_path / 'backup'), \
                 patch.object(maintenance, 'get_config_dir', return_value=temp_path / 'config'), \
                 patch.object(maintenance, 'verify_database_file') as verify_mock, \
                 patch.object(maintenance, 'backup_database', return_value=temp_path / 'backup' / 'database_20260703.db.enc') as backup_mock, \
                 patch.object(maintenance, 'load_database_key') as load_key_mock, \
                 patch.object(maintenance, 'call_command') as call_command_mock, \
                 patch.object(maintenance, 'ensure_roles_and_super_admin') as super_admin_mock:
                result = maintenance.bootstrap_sqlcipher_database()

        runtime_mock.assert_called_once()
        load_key_mock.assert_not_called()
        backup_mock.assert_called_once_with(database_path, temp_path / 'backup')
        call_command_mock.assert_called_once_with('migrate', interactive=False, run_syncdb=True, verbosity=1)
        super_admin_mock.assert_called_once()
        verify_mock.assert_called()
        self.assertEqual(result['database_path'], str(database_path))
        self.assertEqual(result['backup_path'], str(temp_path / 'backup' / 'database_20260703.db.enc'))

    def test_export_and_import_copy_files(self):
        @contextmanager
        def fake_sqlcipher_connection(*_args, **_kwargs):
            class FakeConnection:
                def execute(self, _sql):
                    class FakeCursor:
                        def fetchall(self):
                            return [('ok',)]

                    return FakeCursor()

                def close(self):
                    pass

            yield FakeConnection()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / 'database.db'
            export_path = temp_path / 'export' / 'database_export.db.enc'
            import_target = temp_path / 'imported.db'
            source_path.write_bytes(b'encrypted-bytes')

            def copy_side_effect(source, destination):
                destination_path = Path(destination)
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                destination_path.write_bytes(Path(source).read_bytes())
                return destination_path

            with patch.object(maintenance, 'verify_database_file') as verify_mock, \
                 patch.object(maintenance, 'sqlcipher_connection', fake_sqlcipher_connection), \
                 patch.object(maintenance.shutil, 'copy2', side_effect=copy_side_effect) as copy_mock:
                returned_export_path = maintenance.export_database(export_path, database_path=source_path)
                returned_import_path = maintenance.import_database(source_path, database_path=import_target)

                self.assertEqual(returned_export_path, export_path)
                self.assertEqual(returned_import_path, import_target)
                self.assertTrue(export_path.exists())
                self.assertTrue(import_target.exists())
                self.assertEqual(export_path.read_bytes(), b'encrypted-bytes')
                self.assertEqual(import_target.read_bytes(), b'encrypted-bytes')
                self.assertGreaterEqual(copy_mock.call_count, 2)
                self.assertEqual(verify_mock.call_count, 1)
