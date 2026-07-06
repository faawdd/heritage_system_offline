from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from django.core.management import call_command

from .connection import apply_database_key, sqlcipher_connection, verify_connection
from .key_store import generate_database_key, load_database_key, store_database_key
from .paths import ensure_runtime_directories, get_backup_dir, get_config_dir, get_database_path


ROLE_SUPER_ADMIN = '超级管理员'
ROLE_ADMIN = '管理员'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'Admin@123456'


class SqlCipherMaintenanceError(RuntimeError):
    pass


def _load_admin_bootstrap_password() -> tuple[str, str]:
    username = DEFAULT_ADMIN_USERNAME
    password = (os.environ.get('HERITAGE_BOOTSTRAP_ADMIN_PASSWORD') or '').strip()
    bootstrap_file = get_config_dir() / 'bootstrap-admin.json'
    if bootstrap_file.exists():
        try:
            payload = json.loads(bootstrap_file.read_text(encoding='utf-8'))
            username = str(payload.get('username') or username).strip() or DEFAULT_ADMIN_USERNAME
            if not password:
                password = str(payload.get('password') or '').strip()
        except Exception:
            pass
    if not password:
        password = DEFAULT_ADMIN_PASSWORD
    return username, password


def backup_database(database_path: Path | None = None, backup_dir: Path | None = None) -> Path | None:
    path = Path(database_path or get_database_path())
    if not path.exists():
        return None

    target_dir = Path(backup_dir or get_backup_dir())
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_path = target_dir / f'{path.stem}_{timestamp}{path.suffix}.enc'
    shutil.copy2(path, target_path)
    return target_path


def verify_database_file(database_path: Path | None = None) -> None:
    path = Path(database_path or get_database_path())
    with sqlcipher_connection(path, create_if_missing=not path.exists(), verify=True) as connection:
        verify_connection(connection)


def export_database(destination_path: Path, database_path: Path | None = None) -> Path:
    source_path = Path(database_path or get_database_path())
    if not source_path.exists():
        raise SqlCipherMaintenanceError('Database file not found')

    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    with sqlcipher_connection(destination_path, create_if_missing=False, verify=True) as connection:
        verify_connection(connection)
    return destination_path


def import_database(source_path: Path, database_path: Path | None = None) -> Path:
    source_path = Path(source_path)
    if not source_path.exists():
        raise SqlCipherMaintenanceError('Import source database file not found')

    target_path = Path(database_path or get_database_path())
    target_path.parent.mkdir(parents=True, exist_ok=True)

    backup_path = None
    if target_path.exists():
        backup_path = backup_database(target_path, get_backup_dir())

    shutil.copy2(source_path, target_path)
    try:
        verify_database_file(target_path)
    except Exception as exc:
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, target_path)
        raise SqlCipherMaintenanceError('Imported database failed integrity validation') from exc
    return target_path


def rotate_database_password(database_path: Path | None = None) -> dict:
    path = Path(database_path or get_database_path())
    if not path.exists():
        raise SqlCipherMaintenanceError('Database file not found')

    backup_path = backup_database(path, get_backup_dir())
    current_key = load_database_key(get_config_dir(), create_if_missing=False)
    new_key = generate_database_key()

    with sqlcipher_connection(path, create_if_missing=False, verify=False) as connection:
        apply_database_key(connection, current_key)
        connection.execute(f"PRAGMA rekey = '{new_key}'")
        verify_connection(connection)

    store_database_key(new_key, get_config_dir())
    verify_database_file(path)
    return {'backup_path': str(backup_path) if backup_path else '', 'database_path': str(path)}


def ensure_roles_and_super_admin(config_dir: Path | None = None, logger: logging.Logger | None = None) -> None:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group, Permission

    super_group, _ = Group.objects.get_or_create(name=ROLE_SUPER_ADMIN)
    admin_group, _ = Group.objects.get_or_create(name=ROLE_ADMIN)

    super_group.permissions.set(Permission.objects.all())
    admin_permissions = Permission.objects.exclude(content_type__app_label__in=['auth', 'contenttypes', 'sessions', 'admin'])
    admin_group.permissions.set(admin_permissions)

    user_model = get_user_model()
    username, password = _load_admin_bootstrap_password()

    if not str(os.environ.get('HERITAGE_FORCE_RESET_SUPER_ADMIN_PASSWORD') or '').lower() in {'1', 'true', 'yes', 'on'}:
        has_super_admin = user_model.objects.filter(is_superuser=True, is_active=True).exists() or user_model.objects.filter(
            is_active=True,
            groups__name=ROLE_SUPER_ADMIN,
        ).exists()
        if has_super_admin:
            if logger:
                logger.info('Super admin already exists, skip bootstrap.')
            return

    user = user_model.objects.filter(username=username).first()
    if user is None:
        user = user_model.objects.create_user(
            username=username,
            password=password,
            is_staff=True,
            is_superuser=True,
            is_active=True,
            first_name='超级管理员',
        )
        if logger:
            logger.info('Bootstrap super admin created: %s', username)
    else:
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if not user.first_name:
            user.first_name = '超级管理员'
        user.save()
        if logger:
            logger.info('Existing admin user promoted to super admin: %s', username)

    user.groups.add(super_group)


def bootstrap_sqlcipher_database(logger: logging.Logger | None = None) -> dict:
    ensure_runtime_directories()
    database_path = get_database_path()

    if database_path.exists():
        if logger:
            logger.info('Validating existing SQLCipher database: %s', database_path)
        verify_database_file(database_path)
        backup_path = backup_database(database_path, get_backup_dir())
    else:
        if logger:
            logger.info('Creating SQLCipher database: %s', database_path)
        load_database_key(get_config_dir(), create_if_missing=True)
        backup_path = None

    if logger:
        logger.info('Applying database migrations...')
    call_command('migrate', interactive=False, run_syncdb=True, verbosity=1)

    ensure_roles_and_super_admin(get_config_dir(), logger=logger)
    verify_database_file(database_path)

    return {
        'database_path': str(database_path),
        'backup_path': str(backup_path) if backup_path else '',
    }
