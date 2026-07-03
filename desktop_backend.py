import os
import sys
from pathlib import Path


ROLE_SUPER_ADMIN = '超级管理员'
ROLE_ADMIN = '管理员'


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
    app_dir / '_internal' / 'rasterio' / 'proj_data' / '..' / 'gdal_data',
    app_dir / 'Library' / 'share' / 'gdal',
    app_dir / 'share' / 'gdal',
  ]

  if rasterio_data:
    candidates.insert(0, Path(str(rasterio_data)).resolve())

  for candidate in candidates:
    if candidate.exists():
      os.environ['GDAL_DATA'] = str(candidate)
      return


def _ensure_roles_and_super_admin() -> None:
  from django.contrib.auth import get_user_model
  from django.contrib.auth.models import Group, Permission

  super_group, _ = Group.objects.get_or_create(name=ROLE_SUPER_ADMIN)
  admin_group, _ = Group.objects.get_or_create(name=ROLE_ADMIN)

  all_permissions = Permission.objects.all()
  super_group.permissions.set(all_permissions)

  admin_permissions = Permission.objects.exclude(
    content_type__app_label__in=['auth', 'contenttypes', 'sessions', 'admin']
  )
  admin_group.permissions.set(admin_permissions)

  User = get_user_model()
  has_super_admin = User.objects.filter(is_superuser=True, is_active=True).exists() or User.objects.filter(
    is_active=True,
    groups__name=ROLE_SUPER_ADMIN,
  ).exists()

  if has_super_admin:
    return

  bootstrap_password = (os.environ.get('HERITAGE_BOOTSTRAP_ADMIN_PASSWORD') or '').strip()
  if not bootstrap_password:
    raise RuntimeError('No super admin account found and no bootstrap password provided. Complete first-run wizard and set admin password.')

  user = User.objects.filter(username='admin').first()
  if user is None:
    user = User.objects.create_user(
      username='admin',
      password=bootstrap_password,
      is_staff=True,
      is_superuser=True,
      is_active=True,
      first_name='超级管理员',
    )
  else:
    user.set_password(bootstrap_password)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    if not user.first_name:
      user.first_name = '超级管理员'
    user.save()

  user.groups.add(super_group)


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
  from django.core.servers.basehttp import run
  from django.core.wsgi import get_wsgi_application

  execute_from_command_line(['desktop_backend.py', 'migrate', '--noinput'])
  _ensure_roles_and_super_admin()

  if getattr(sys, 'frozen', False):
    application = get_wsgi_application()
    run(host, int(port), application, threading=True)
    return

  runserver_args = ['desktop_backend.py', 'runserver', f'{host}:{port}', '--noreload']
  execute_from_command_line(runserver_args)


if __name__ == '__main__':
  main()
