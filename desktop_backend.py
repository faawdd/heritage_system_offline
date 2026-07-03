import os
import sys
from pathlib import Path


def _resolve_base_dir() -> Path:
  if getattr(sys, 'frozen', False):
    return Path(sys.executable).resolve().parent
  return Path(__file__).resolve().parent


def main() -> None:
  base_dir = _resolve_base_dir()
  os.chdir(base_dir)
  sys.path.insert(0, str(base_dir))

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
  os.environ.setdefault('DJANGO_DEBUG', '0')
  os.environ.setdefault('DJANGO_FORCE_HTTPS', '0')

  host = os.environ.get('BACKEND_HOST', '127.0.0.1')
  port = os.environ.get('BACKEND_PORT', '18000')
  os.environ.setdefault('DJANGO_WEB_BASE_URL', f'http://{host}:{port}')

  from django.core.management import execute_from_command_line

  execute_from_command_line(['desktop_backend.py', 'migrate', '--noinput'])
  execute_from_command_line(['desktop_backend.py', 'runserver', f'{host}:{port}'])


if __name__ == '__main__':
  main()
