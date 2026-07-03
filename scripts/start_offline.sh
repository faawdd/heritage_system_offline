#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

BIND_HOST="127.0.0.1"
PORT="8000"
INIT_DEPS="0"
OPEN_BROWSER="1"

choose_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return
  fi
  if command -v python3.10 >/dev/null 2>&1; then
    echo "python3.10"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  echo ""
}

python_is_supported() {
  local py_cmd="$1"
  "$py_cmd" -c 'import sys; raise SystemExit(0 if (sys.version_info.major > 3 or (sys.version_info.major == 3 and sys.version_info.minor >= 10)) else 1)'
}

python_version_text() {
  local py_cmd="$1"
  "$py_cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --init-deps|-i)
      INIT_DEPS="1"
      shift
      ;;
    --host)
      BIND_HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --no-browser)
      OPEN_BROWSER="0"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/start_offline.sh [options]

Options:
  --init-deps, -i      Install dependencies from requirements.txt
  --host <host>        Bind host (default: 127.0.0.1)
  --port <port>        Bind port (default: 8000)
  --no-browser         Do not open browser automatically
  --help, -h           Show this help
EOF
      exit 0
      ;;
    *)
      echo "[offline] Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

PYTHON_CMD="$(choose_python)"
if [[ -z "$PYTHON_CMD" ]]; then
  echo "[offline] Python 3 is not installed or not in PATH." >&2
  exit 1
fi

if ! python_is_supported "$PYTHON_CMD"; then
  echo "[offline] Detected $(python_version_text "$PYTHON_CMD"), but Python >= 3.10 is required." >&2
  echo "[offline] Please install python3.10+ (recommended: python3.11)." >&2
  exit 1
fi

echo "[offline] Using ${PYTHON_CMD} ($(python_version_text "$PYTHON_CMD"))"

if [[ -x ".venv/bin/python" ]] && ! python_is_supported ".venv/bin/python"; then
  echo "[offline] Existing .venv uses unsupported Python ($(python_version_text ".venv/bin/python")); recreating..."
  rm -rf .venv
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "[offline] Creating virtual environment (.venv)..."
  "$PYTHON_CMD" -m venv .venv
fi

PYTHON_EXE="$PROJECT_ROOT/.venv/bin/python"

echo "[offline] Upgrading pip..."
"$PYTHON_EXE" -m pip install --upgrade pip

if [[ "$INIT_DEPS" == "1" ]]; then
  echo "[offline] Installing dependencies from requirements.txt..."
  "$PYTHON_EXE" -m pip install -r requirements.txt
fi

export DJANGO_DEBUG="1"
export DJANGO_FORCE_HTTPS="0"
export DJANGO_WEB_BASE_URL="http://${BIND_HOST}:${PORT}"

echo "[offline] Running database migrations..."
"$PYTHON_EXE" manage.py migrate --noinput

echo "[offline] Ensuring debug super admin account (test/test)..."
"$PYTHON_EXE" manage.py shell -c "from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group, Permission; ROLE_SUPER_ADMIN='超级管理员'; ROLE_ADMIN='管理员'; User=get_user_model(); super_group,_=Group.objects.get_or_create(name=ROLE_SUPER_ADMIN); admin_group,_=Group.objects.get_or_create(name=ROLE_ADMIN); super_group.permissions.set(Permission.objects.all()); admin_group.permissions.set(Permission.objects.exclude(content_type__app_label__in=['auth','contenttypes','sessions','admin'])); user,created=User.objects.get_or_create(username='test', defaults={'is_staff':True,'is_superuser':True,'is_active':True,'first_name':'调试账号'}); user.is_staff=True; user.is_superuser=True; user.is_active=True; user.set_password('test'); user.save(); user.groups.add(super_group); print('debug user ensured: test')"

URL="http://${BIND_HOST}:${PORT}/"
if [[ "$OPEN_BROWSER" == "1" ]]; then
  echo "[offline] Opening browser: ${URL}"
  if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  fi
fi

echo "[offline] Starting Django server at ${BIND_HOST}:${PORT}"
exec "$PYTHON_EXE" manage.py runserver "${BIND_HOST}:${PORT}"
