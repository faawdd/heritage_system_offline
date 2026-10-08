#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${1:-desktop_runtime}"
BUILD_ROOT="$PROJECT_ROOT/.desktop-build"

cd "$PROJECT_ROOT"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

"$PYTHON_BIN" -m pip install -r requirements.txt -r requirements-desktop.txt

if [[ ! -f static/frontend/index.html ]]; then
  echo "Missing frontend bundle: static/frontend/index.html" >&2
  echo "Run npm --prefix frontend run build first." >&2
  exit 1
fi

"$PYTHON_BIN" -m PyInstaller \
  desktop_backend.py \
  --name heritage_backend \
  --noconfirm \
  --clean \
  --onedir \
  --distpath "$BUILD_ROOT/dist" \
  --workpath "$BUILD_ROOT/work" \
  --specpath "$BUILD_ROOT/spec" \
  --add-data "$PROJECT_ROOT/static:static" \
  --add-data "$PROJECT_ROOT/templates:templates" \
  --collect-all django \
  --collect-all rest_framework \
  --collect-all rest_framework_simplejwt \
  --collect-all import_export \
  --collect-all rasterio \
  --collect-all waitress \
  --collect-all whitenoise \
  --collect-submodules core \
  --collect-submodules system \
  --collect-submodules heritage_system

APP_DIR="$PROJECT_ROOT/$OUTPUT_ROOT/app"
mkdir -p "$APP_DIR"
cp -R "$BUILD_ROOT/dist/heritage_backend/." "$APP_DIR/"
cp -R static "$APP_DIR/"
cp -R templates "$APP_DIR/"
echo "Desktop runtime ready: $APP_DIR"