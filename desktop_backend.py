import json
import logging
import os
import sys
from pathlib import Path

ROLE_SUPER_ADMIN = '超级管理员'
ROLE_ADMIN = '管理员'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'Admin@123456'
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

    db_file = Path(os.environ.get('HERITAGE_DB_FILE', data_dir / 'database.db')).resolve()
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
    from heritage_system.sqlcipher.maintenance import bootstrap_sqlcipher_database

    bootstrap_sqlcipher_database(logger=logger)
    _start_waitress(host, port, logger)

    logger.info('Backend started successfully')
    return 0
  except Exception:
    logger.exception('Backend startup failed')
    return 1


if __name__ == '__main__':
  sys.exit(main())
