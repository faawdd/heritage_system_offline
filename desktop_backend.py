import os
import sys
from pathlib import Path


def _resolve_base_dir() -> Path:
  if getattr(sys, 'frozen', False):
    return Path(sys.executable).resolve().parent
  return Path(__file__).resolve().parent


def _resolve_runtime_dirs(base_dir: Path) -> tuple[Path, Path, Path]:
  if getattr(sys, 'frozen', False):
    app_dir = base_dir
    runtime_root = app_dir.parent
  else:
    app_dir = base_dir
    runtime_root = base_dir

  data_dir = Path(os.environ.get('HERITAGE_DATA_DIR', runtime_root / 'data')).resolve()
  config_dir = Path(os.environ.get('HERITAGE_CONFIG_DIR', runtime_root / 'config')).resolve()
  app_dir = Path(os.environ.get('HERITAGE_APP_DIR', app_dir)).resolve()
  return app_dir, data_dir, config_dir


def _configure_gdal_data(app_dir: Path) -> None:
  if os.environ.get('GDAL_DATA'):
    return

  candidates = [
    app_dir / 'gdal-data',
    app_dir / 'Library' / 'share' / 'gdal',
    app_dir / 'share' / 'gdal',
  ]

  for candidate in candidates:
    if candidate.exists():
      os.environ['GDAL_DATA'] = str(candidate)
      return


def main() -> None:
  base_dir = _resolve_base_dir()
  app_dir, data_dir, config_dir = _resolve_runtime_dirs(base_dir)

  data_dir.mkdir(parents=True, exist_ok=True)
  config_dir.mkdir(parents=True, exist_ok=True)

  os.chdir(app_dir)
  sys.path.insert(0, str(app_dir))

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
  os.environ.setdefault('DJANGO_DEBUG', '0')
  os.environ.setdefault('DJANGO_FORCE_HTTPS', '0')
  os.environ.setdefault('HERITAGE_APP_DIR', str(app_dir))
  os.environ.setdefault('HERITAGE_DATA_DIR', str(data_dir))
  os.environ.setdefault('HERITAGE_CONFIG_DIR', str(config_dir))
  _configure_gdal_data(app_dir)

  host = os.environ.get('BACKEND_HOST', '127.0.0.1')
  port = os.environ.get('BACKEND_PORT', '18000')
  os.environ.setdefault('DJANGO_WEB_BASE_URL', f'http://{host}:{port}')

  from django.core.management import execute_from_command_line

  execute_from_command_line(['desktop_backend.py', 'migrate', '--noinput'])

  runserver_args = ['desktop_backend.py', 'runserver', f'{host}:{port}', '--noreload']
  if getattr(sys, 'frozen', False):
    runserver_args.append('--nothreading')

  execute_from_command_line(runserver_args)


if __name__ == '__main__':
  main()
