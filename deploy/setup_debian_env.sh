#!/usr/bin/env bash
# Debian environment bootstrap for heritage_system 2.0
# - Installs system dependencies
# - Creates Python virtualenv and installs requirements
# - Optionally builds frontend assets
# - Optionally writes and enables systemd services: heritage / heritage_fastapi

set -Eeuo pipefail

PROJECT_DIR="/home/flower/heritage_system"
APP_USER="flower"
APP_GROUP="flower"
PYTHON_BIN="python3"
INSTALL_NODE="yes"
BUILD_FRONTEND="yes"
WRITE_SERVICES="yes"
ENABLE_SERVICES="yes"
GUNICORN_BIND="127.0.0.1:8001"
FASTAPI_BIND="127.0.0.1"
FASTAPI_PORT="8000"

usage() {
  cat <<'USAGE'
Usage:
  sudo bash deploy/setup_debian_env.sh [options]

Options:
  --project-dir <path>        Project path (default: /home/flower/heritage_system)
  --user <name>               Service user (default: flower)
  --group <name>              Service group (default: flower)
  --python-bin <bin>          Python executable (default: python3)
  --install-node <yes|no>     Install Node.js if missing/old (default: yes)
  --build-frontend <yes|no>   Build frontend assets (default: yes)
  --write-services <yes|no>   Write systemd service files (default: yes)
  --enable-services <yes|no>  Enable and restart services (default: yes)
  --gunicorn-bind <ip:port>   Django gunicorn bind (default: 127.0.0.1:8001)
  --fastapi-bind <ip>         FastAPI bind host (default: 127.0.0.1)
  --fastapi-port <port>       FastAPI bind port (default: 8000)
  -h, --help                  Show this help
USAGE
}

log() {
  echo "[setup] $*"
}

require_root() {
  if [ "${EUID}" -ne 0 ]; then
    echo "Please run as root: sudo bash deploy/setup_debian_env.sh"
    exit 1
  fi
}

resolve_runtime_user_group() {
  local fallback_user
  fallback_user="${SUDO_USER:-}"

  if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
    if [ -n "$fallback_user" ] && getent group "$fallback_user" >/dev/null 2>&1; then
      log "Group '$APP_GROUP' not found, fallback to '$fallback_user'."
      APP_GROUP="$fallback_user"
    else
      log "Group '$APP_GROUP' not found, creating it..."
      groupadd "$APP_GROUP"
    fi
  fi

  if ! id -u "$APP_USER" >/dev/null 2>&1; then
    if [ -n "$fallback_user" ] && id -u "$fallback_user" >/dev/null 2>&1; then
      log "User '$APP_USER' not found, fallback to '$fallback_user'."
      APP_USER="$fallback_user"
    else
      echo "User '$APP_USER' not found and no valid SUDO_USER fallback detected."
      echo "Please create user first, or run with --user/--group existing account."
      exit 1
    fi
  fi

  # Ensure the effective group exists after possible user fallback.
  if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
    log "Group '$APP_GROUP' still not found, creating it..."
    groupadd "$APP_GROUP"
  fi

  # If APP_USER has no primary group match and desired group exists, continue using desired group.
  log "Using runtime account: ${APP_USER}:${APP_GROUP}"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --project-dir)
        PROJECT_DIR="$2"; shift 2 ;;
      --user)
        APP_USER="$2"; shift 2 ;;
      --group)
        APP_GROUP="$2"; shift 2 ;;
      --python-bin)
        PYTHON_BIN="$2"; shift 2 ;;
      --install-node)
        INSTALL_NODE="$2"; shift 2 ;;
      --build-frontend)
        BUILD_FRONTEND="$2"; shift 2 ;;
      --write-services)
        WRITE_SERVICES="$2"; shift 2 ;;
      --enable-services)
        ENABLE_SERVICES="$2"; shift 2 ;;
      --gunicorn-bind)
        GUNICORN_BIND="$2"; shift 2 ;;
      --fastapi-bind)
        FASTAPI_BIND="$2"; shift 2 ;;
      --fastapi-port)
        FASTAPI_PORT="$2"; shift 2 ;;
      -h|--help)
        usage; exit 0 ;;
      *)
        echo "Unknown option: $1"
        usage
        exit 1 ;;
    esac
  done
}

install_apt_packages() {
  log "Installing apt packages..."
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates gnupg lsb-release \
    build-essential pkg-config \
    "$PYTHON_BIN" python3-venv python3-dev python3-pip \
    libssl-dev libffi-dev zlib1g-dev libjpeg-dev \
    libxml2-dev libxslt1-dev \
    gdal-bin libgdal-dev libproj-dev proj-bin libgeos-dev \
    nginx
}

ensure_node() {
  if [ "$INSTALL_NODE" != "yes" ]; then
    log "Skipping Node.js install (--install-node=no)."
    return
  fi

  local need_install="no"
  if ! command -v node >/dev/null 2>&1; then
    need_install="yes"
  else
    local major
    major="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
    if [ -z "$major" ] || [ "$major" -lt 18 ]; then
      need_install="yes"
    fi
  fi

  if [ "$need_install" = "yes" ]; then
    log "Installing Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
  else
    log "Node.js is already available: $(node -v)"
  fi
}

prepare_project_permissions() {
  if [ ! -d "$PROJECT_DIR" ]; then
    echo "Project directory not found: $PROJECT_DIR"
    exit 1
  fi

  log "Preparing directories and permissions..."
  mkdir -p "$PROJECT_DIR"/logs
  mkdir -p "$PROJECT_DIR"/media
  mkdir -p "$PROJECT_DIR"/staticfiles
  chown -R "$APP_USER":"$APP_GROUP" "$PROJECT_DIR"
}

setup_python_env() {
  log "Setting up Python virtual environment..."
  cd "$PROJECT_DIR"

  if [ ! -d .venv ]; then
    sudo -u "$APP_USER" "$PYTHON_BIN" -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip wheel setuptools

  if [ -f requirements.txt ]; then
    pip install -r requirements.txt
  fi
  if [ -f fastapi_server/requirements.txt ]; then
    pip install -r fastapi_server/requirements.txt
  fi

  # settings.py 默认 USE_LEGACY_ADMIN_UI=1，会在 INSTALLED_APPS 中启用 simpleui
  # 这里做显式兜底，避免迁移阶段报 ModuleNotFoundError: simpleui
  if ! pip show django-simpleui >/dev/null 2>&1; then
    log "Installing django-simpleui for legacy admin UI compatibility..."
    if ! pip install django-simpleui; then
      echo "❌ django-simpleui 安装失败。"
      echo "如果你不使用 legacy admin UI，请在 $PROJECT_DIR/.env 写入: USE_LEGACY_ADMIN_UI=0"
      exit 1
    fi
  fi
}

run_django_tasks() {
  log "Running Django migrations and collectstatic..."
  cd "$PROJECT_DIR"

  # shellcheck disable=SC1091
  source .venv/bin/activate

  sudo -u "$APP_USER" env PATH="$PROJECT_DIR/.venv/bin:$PATH" \
    "$PROJECT_DIR/.venv/bin/python" manage.py migrate --no-input

  sudo -u "$APP_USER" env PATH="$PROJECT_DIR/.venv/bin:$PATH" \
    "$PROJECT_DIR/.venv/bin/python" manage.py collectstatic --noinput
}

build_frontend() {
  if [ "$BUILD_FRONTEND" != "yes" ]; then
    log "Skipping frontend build (--build-frontend=no)."
    return
  fi

  if [ ! -f "$PROJECT_DIR/frontend/package.json" ]; then
    log "frontend/package.json not found, skipping frontend build."
    return
  fi

  log "Building frontend assets..."
  cd "$PROJECT_DIR/frontend"
  sudo -u "$APP_USER" npm ci
  sudo -u "$APP_USER" npm run build
}

write_service_files() {
  if [ "$WRITE_SERVICES" != "yes" ]; then
    log "Skipping systemd service file generation (--write-services=no)."
    return
  fi

  log "Writing systemd service files..."

  cat > /etc/systemd/system/heritage.service <<EOF
[Unit]
Description=Heritage Django Gunicorn Service
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$PROJECT_DIR
Environment=DJANGO_SETTINGS_MODULE=heritage_system.settings
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn heritage_system.wsgi:application --workers 3 --bind $GUNICORN_BIND --timeout 120 --access-logfile $PROJECT_DIR/logs/gunicorn_access.log --error-logfile $PROJECT_DIR/logs/gunicorn_error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  cat > /etc/systemd/system/heritage_fastapi.service <<EOF
[Unit]
Description=Heritage FastAPI Service
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$PROJECT_DIR/fastapi_server
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/.venv/bin/uvicorn main:app --host $FASTAPI_BIND --port $FASTAPI_PORT --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
}

enable_services() {
  if [ "$ENABLE_SERVICES" != "yes" ]; then
    log "Skipping service enable/restart (--enable-services=no)."
    return
  fi

  log "Enabling and restarting services..."
  systemctl enable heritage
  systemctl enable heritage_fastapi
  systemctl restart heritage
  systemctl restart heritage_fastapi
}

show_summary() {
  cat <<EOF

====================================
Debian environment setup completed.
====================================
Project: $PROJECT_DIR
User: $APP_USER:$APP_GROUP
Django bind: $GUNICORN_BIND
FastAPI bind: $FASTAPI_BIND:$FASTAPI_PORT

Check status:
  sudo systemctl status heritage --no-pager
  sudo systemctl status heritage_fastapi --no-pager

Follow-up (manual):
1) Configure Nginx reverse proxy to:
   - Django:  $GUNICORN_BIND
   - FastAPI: $FASTAPI_BIND:$FASTAPI_PORT
2) Configure HTTPS certificate (certbot or existing TLS).
3) If you use .env, create $PROJECT_DIR/.env and fill production variables.
EOF
}

main() {
  require_root
  parse_args "$@"
  resolve_runtime_user_group

  install_apt_packages
  ensure_node
  prepare_project_permissions
  setup_python_env
  run_django_tasks
  build_frontend
  write_service_files
  enable_services
  show_summary
}

main "$@"
