#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${1:-desktop_runtime}"

cd "$PROJECT_ROOT"

PYTHON_BIN=""
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
elif command -v python3.10 >/dev/null 2>&1; then
  PYTHON_BIN="python3.10"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "[desktop-runtime] ERROR: Python 3 is required." >&2
  exit 1
fi

PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_MAJOR="${PYTHON_VERSION%%.*}"
PYTHON_MINOR="${PYTHON_VERSION##*.}"
if [[ "$PYTHON_MAJOR" -lt 3 || ( "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ) ]]; then
  echo "[desktop-runtime] ERROR: $PYTHON_BIN is Python $PYTHON_VERSION, but Python >= 3.10 is required (Django>=5)." >&2
  echo "[desktop-runtime] Please install Python 3.10+ or create .venv with Python 3.10+ and retry." >&2
  exit 1
fi

echo "[desktop-runtime] Using Python: $PYTHON_BIN (version $PYTHON_VERSION)"

echo "[desktop-runtime] Installing build tools..."
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" -m pip install pyinstaller

echo "[desktop-runtime] Building backend executable..."
"$PYTHON_BIN" -m PyInstaller \
  desktop_backend.py \
  --name heritage_backend \
  --noconfirm \
  --clean \
  --collect-data rasterio \
  --hidden-import sqlite3 \
  --hidden-import heritage_system.db.backends.sqlcipher \
  --hidden-import heritage_system.db.backends.sqlcipher.base \
  --collect-all sqlcipher3 \
  --collect-all cryptography \
  --collect-all keyring \
  --onedir

OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_ROOT"
APP_DIR="$OUTPUT_DIR/app"
DATA_DIR="$OUTPUT_DIR/data"
CONFIG_DIR="$OUTPUT_DIR/config"

FRONTEND_INDEX="$PROJECT_ROOT/static/frontend/index.html"
if [[ ! -f "$FRONTEND_INDEX" ]]; then
  echo "[desktop-runtime] ERROR: Missing frontend bundle at static/frontend/index.html" >&2
  echo "[desktop-runtime] Run: cd frontend && npm run build" >&2
  exit 1
fi

rm -rf "$OUTPUT_DIR"
mkdir -p "$APP_DIR" "$DATA_DIR" "$CONFIG_DIR"

cp -R dist/heritage_backend/. "$APP_DIR/"
[[ -d static ]] && cp -R static "$APP_DIR/"
[[ -d templates ]] && cp -R templates "$APP_DIR/"
[[ -f .env.example ]] && cp .env.example "$CONFIG_DIR/"

echo "[desktop-runtime] Runtime is ready: $OUTPUT_DIR (app/data/config)"
echo "[desktop-runtime] Next: cd frontend && npm run desktop:pack"
