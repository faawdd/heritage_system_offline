#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${1:-desktop_runtime}"

cd "$PROJECT_ROOT"

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

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
  --onedir

OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_ROOT"
APP_DIR="$OUTPUT_DIR/app"
DATA_DIR="$OUTPUT_DIR/data"
CONFIG_DIR="$OUTPUT_DIR/config"

rm -rf "$OUTPUT_DIR"
mkdir -p "$APP_DIR" "$DATA_DIR" "$CONFIG_DIR"

cp -R dist/heritage_backend/. "$APP_DIR/"
[[ -d static ]] && cp -R static "$APP_DIR/"
[[ -d templates ]] && cp -R templates "$APP_DIR/"
[[ -f .env.example ]] && cp .env.example "$CONFIG_DIR/"

echo "[desktop-runtime] Runtime is ready: $OUTPUT_DIR (app/data/config)"
echo "[desktop-runtime] Next: cd frontend && npm run desktop:pack"
