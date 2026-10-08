from __future__ import annotations

import logging
import json
import os
import sys
from pathlib import Path


def _configure_runtime() -> tuple[Path, Path, Path]:
    app_dir = Path(os.environ.get('HERITAGE_APP_DIR') or Path(__file__).resolve().parent).resolve()
    user_data_dir = Path(os.environ.get('HERITAGE_DATA_DIR') or Path.home() / '.heritage-system').resolve()
    upload_dir = Path(os.environ.get('HERITAGE_UPLOAD_DIR') or user_data_dir / 'media').resolve()
    log_dir = Path(os.environ.get('HERITAGE_LOG_DIR') or user_data_dir / 'logs').resolve()

    for directory in (user_data_dir, upload_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ['HERITAGE_DESKTOP_MODE'] = '1'
    os.environ['HERITAGE_APP_DIR'] = str(app_dir)
    os.environ['HERITAGE_DATA_DIR'] = str(user_data_dir)
    os.environ['HERITAGE_DB_FILE'] = str(user_data_dir / 'database.sqlite3')
    os.environ['HERITAGE_UPLOAD_DIR'] = str(upload_dir)
    os.environ['HERITAGE_LOG_DIR'] = str(log_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
    os.environ['DJANGO_DEBUG'] = '0'
    os.environ.setdefault('DJANGO_FORCE_HTTPS', '0')
    os.environ.setdefault('REPORT_AUTO_GENERATOR_ENABLED', 'false')
    os.chdir(app_dir)
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    return app_dir, user_data_dir, log_dir


def _ensure_initial_admin(logger: logging.Logger) -> None:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group, Permission

    from core.models import UserProfile
    from core.services.account_security import hash_security_questions

    raw_security_questions = (
        os.environ.pop('HERITAGE_BOOTSTRAP_SECURITY_QUESTIONS', '').strip()
        or sys.stdin.readline().strip()
        or '[]'
    )
    user_model = get_user_model()
    existing_superuser = user_model.objects.filter(is_active=True, is_superuser=True).first()
    if not existing_superuser:
        try:
            hashed_questions = hash_security_questions(json.loads(raw_security_questions))
        except Exception as exc:
            raise RuntimeError('首次启动必须配置 3 个不同的密码保护问题') from exc
        user, created = user_model.objects.get_or_create(
            username='admin',
            defaults={
                'is_active': True,
                'is_staff': True,
                'is_superuser': True,
                'first_name': '超级管理员',
            },
        )
        if created:
            user.set_password('admin')
            user.save(update_fields=['password'])
        else:
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['is_active', 'is_staff', 'is_superuser'])

        super_admin_group, _ = Group.objects.get_or_create(name='超级管理员')
        super_admin_group.permissions.set(Permission.objects.all())
        user.groups.add(super_admin_group)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.has_changed_password = False
        profile.security_questions = hashed_questions
        profile.save(update_fields=['has_changed_password', 'security_questions'])
        logger.warning('Initial super administrator is ready; password change is required after first login.')
    else:
        profile, _ = UserProfile.objects.get_or_create(user=existing_superuser)
        if not profile.security_questions:
            try:
                profile.security_questions = hash_security_questions(json.loads(raw_security_questions))
            except Exception as exc:
                raise RuntimeError('请完成管理员安全问题配置后启动离线系统') from exc
            profile.save(update_fields=['security_questions'])


def main() -> int:
    _, _, log_dir = _configure_runtime()
    logging.basicConfig(
        filename=log_dir / 'backend.log',
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )
    logger = logging.getLogger('desktop_backend')

    try:
        import django
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from waitress import serve

        django.setup()
        call_command('migrate', interactive=False, verbosity=0)
        _ensure_initial_admin(logger)
        host = os.environ.get('BACKEND_HOST', '127.0.0.1')
        port = int(os.environ.get('BACKEND_PORT', '18000'))
        logger.info('Starting local WSGI server on %s:%s', host, port)
        serve(get_wsgi_application(), host=host, port=port, threads=8)
        return 0
    except Exception:
        logger.exception('Desktop backend failed to start')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())