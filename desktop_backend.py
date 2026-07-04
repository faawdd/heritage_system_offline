import json
import logging
import os
import sys
from pathlib import Path

ROLE_SUPER_ADMIN = '超级管理员'
ROLE_ADMIN = '管理员'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'Admin@123456'
FORCE_RESET_SUPER_ADMIN_PASSWORD = str(os.environ.get('HERITAGE_FORCE_RESET_SUPER_ADMIN_PASSWORD') or '').lower() in {'1', 'true', 'yes', 'on'}
OFFLINE_DEBUG_MODE = str(os.environ.get('HERITAGE_OFFLINE_DEBUG') or '').lower() in {'1', 'true', 'yes', 'on'}
OFFLINE_DEBUG_USERNAME = 'test'
OFFLINE_DEBUG_PASSWORD = 'test'


def _resolve_base_dir() -> Path:
  if getattr(sys, 'frozen', False):
    return Path(sys.executable).resolve().parent
  return Path(__file__).resolve().parent


def _resolve_runtime_dirs(base_dir: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
  if getattr(sys, 'frozen', False):
    app_dir = base_dir
    runtime_root = app_dir.parent
  else:
    app_dir = base_dir
    runtime_root = base_dir

  app_dir = Path(os.environ.get('HERITAGE_APP_DIR', app_dir)).resolve()
  data_dir = Path(os.environ.get('HERITAGE_DATA_DIR', runtime_root / 'data')).resolve()
  config_dir = Path(os.environ.get('HERITAGE_CONFIG_DIR', runtime_root / 'config')).resolve()
  log_dir = Path(os.environ.get('HERITAGE_LOG_DIR', runtime_root / 'logs')).resolve()
  uploads_dir = Path(os.environ.get('HERITAGE_UPLOAD_DIR', runtime_root / 'uploads')).resolve()
  backup_dir = Path(os.environ.get('HERITAGE_BACKUP_DIR', runtime_root / 'backup')).resolve()
  return app_dir, data_dir, config_dir, log_dir, uploads_dir, backup_dir


def _setup_logging(log_dir: Path) -> logging.Logger:
  log_dir.mkdir(parents=True, exist_ok=True)
  log_file = log_dir / 'backend.log'

  logger = logging.getLogger('desktop_backend')
  logger.setLevel(logging.INFO)
  logger.handlers.clear()

  formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

  file_handler = logging.FileHandler(log_file, encoding='utf-8')
  file_handler.setFormatter(formatter)
  logger.addHandler(file_handler)

  stream_handler = logging.StreamHandler(sys.stdout)
  stream_handler.setFormatter(formatter)
  logger.addHandler(stream_handler)

  return logger


def _configure_gdal_data(app_dir: Path, logger: logging.Logger) -> None:
  if os.environ.get('GDAL_DATA'):
    return

  rasterio_data = None
  try:
    import rasterio

    rasterio_data = getattr(rasterio, '__gdal_data__', None)
  except Exception:
    rasterio_data = None

  candidates = [
    app_dir / 'gdal-data',
    app_dir / 'gdal_data',
    app_dir / '_internal' / 'rasterio' / 'gdal_data',
    app_dir / 'Library' / 'share' / 'gdal',
    app_dir / 'share' / 'gdal',
  ]

  if rasterio_data:
    candidates.insert(0, Path(str(rasterio_data)).resolve())

  for candidate in candidates:
    if candidate.exists():
      os.environ['GDAL_DATA'] = str(candidate)
      logger.info('GDAL_DATA set to: %s', candidate)
      return

  logger.warning('GDAL_DATA not found in packaged paths; some raster features may be limited.')


def _load_admin_bootstrap(config_dir: Path, logger: logging.Logger) -> tuple[str, str]:
  if OFFLINE_DEBUG_MODE:
    return OFFLINE_DEBUG_USERNAME, OFFLINE_DEBUG_PASSWORD

  username = DEFAULT_ADMIN_USERNAME
  password = (os.environ.get('HERITAGE_BOOTSTRAP_ADMIN_PASSWORD') or '').strip()

  bootstrap_file = config_dir / 'bootstrap-admin.json'
  if bootstrap_file.exists():
    try:
      payload = json.loads(bootstrap_file.read_text(encoding='utf-8'))
      username = str(payload.get('username') or username).strip() or DEFAULT_ADMIN_USERNAME
      if not password:
        password = str(payload.get('password') or '').strip()
    except Exception:
      logger.exception('Failed to parse bootstrap-admin.json, fallback to defaults.')

  if not password:
    password = DEFAULT_ADMIN_PASSWORD

  return username, password


def _ensure_roles_and_super_admin(config_dir: Path, logger: logging.Logger) -> None:
  from django.contrib.auth import get_user_model
  from django.contrib.auth.models import Group, Permission

  super_group, _ = Group.objects.get_or_create(name=ROLE_SUPER_ADMIN)
  admin_group, _ = Group.objects.get_or_create(name=ROLE_ADMIN)

  all_permissions = Permission.objects.all()
  super_group.permissions.set(all_permissions)
  admin_permissions = Permission.objects.exclude(content_type__app_label__in=['auth', 'contenttypes', 'sessions', 'admin'])
  admin_group.permissions.set(admin_permissions)

  User = get_user_model()
  username, password = _load_admin_bootstrap(config_dir, logger)
  if not OFFLINE_DEBUG_MODE and not FORCE_RESET_SUPER_ADMIN_PASSWORD:
    has_super_admin = User.objects.filter(is_superuser=True, is_active=True).exists() or User.objects.filter(
      is_active=True,
      groups__name=ROLE_SUPER_ADMIN,
    ).exists()

    if has_super_admin:
      logger.info('Super admin already exists, skip bootstrap.')
      return

  user = User.objects.filter(username=username).first()
  if user is None:
    user = User.objects.create_user(
      username=username,
      password=password,
      is_staff=True,
      is_superuser=True,
      is_active=True,
      first_name='超级管理员',
    )
    logger.info('Bootstrap super admin created: %s', username)
  else:
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    if not user.first_name:
      user.first_name = '超级管理员'
    user.save()
    if FORCE_RESET_SUPER_ADMIN_PASSWORD:
      logger.info('Existing super admin password force-reset: %s', username)
    else:
      logger.info('Existing admin user promoted to super admin: %s', username)

  user.groups.add(super_group)


def _apply_migrations(logger: logging.Logger) -> None:
  from django.core.management import call_command

  logger.info('Applying database migrations...')
  call_command('migrate', interactive=False, run_syncdb=True, verbosity=1)
  logger.info('Database migrations applied.')


def _start_waitress(host: str, port: int, logger: logging.Logger) -> None:
  from django.core.wsgi import get_wsgi_application
  from waitress import serve

  application = get_wsgi_application()
  logger.info('Starting Waitress on %s:%s', host, port)
  serve(application, host=host, port=port, threads=8)


def main() -> int:
  base_dir = _resolve_base_dir()
  app_dir, data_dir, config_dir, log_dir, uploads_dir, backup_dir = _resolve_runtime_dirs(base_dir)

  logger = _setup_logging(log_dir)

  try:
    for path in [data_dir, config_dir, log_dir, uploads_dir, backup_dir]:
      path.mkdir(parents=True, exist_ok=True)

    db_file = Path(os.environ.get('HERITAGE_DB_FILE', data_dir / 'database.sqlite3')).resolve()
    db_file.parent.mkdir(parents=True, exist_ok=True)

    os.chdir(app_dir)
    if str(app_dir) not in sys.path:
      sys.path.insert(0, str(app_dir))

    host = os.environ.get('BACKEND_HOST', '127.0.0.1')
    port = int(os.environ.get('BACKEND_PORT', '8000'))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
    os.environ['DJANGO_DEBUG'] = '1'
    os.environ.setdefault('DJANGO_FORCE_HTTPS', '0')
    os.environ['HERITAGE_DESKTOP_MODE'] = '1'
    os.environ['HERITAGE_APP_DIR'] = str(app_dir)
    os.environ['HERITAGE_DATA_DIR'] = str(data_dir)
    os.environ['HERITAGE_CONFIG_DIR'] = str(config_dir)
    os.environ['HERITAGE_LOG_DIR'] = str(log_dir)
    os.environ['HERITAGE_UPLOAD_DIR'] = str(uploads_dir)
    os.environ['HERITAGE_BACKUP_DIR'] = str(backup_dir)
    os.environ['HERITAGE_DB_FILE'] = str(db_file)
    os.environ.setdefault('DJANGO_WEB_BASE_URL', f'http://{host}:{port}')

    _configure_gdal_data(app_dir, logger)

    import django

    django.setup()
    _apply_migrations(logger)
    _ensure_roles_and_super_admin(config_dir, logger)
    _start_waitress(host, port, logger)

    logger.info('Backend started successfully')
    return 0
  except Exception:
    logger.exception('Backend startup failed')
    return 1


if __name__ == '__main__':
  sys.exit(main())
