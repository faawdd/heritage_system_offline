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
BACKEND_DIR="$OUTPUT_DIR/backend"

rm -rf "$OUTPUT_DIR"
mkdir -p "$BACKEND_DIR"

cp -R dist/heritage_backend/. "$BACKEND_DIR/"
cp db.sqlite3 "$BACKEND_DIR/"
[[ -d media ]] && cp -R media "$BACKEND_DIR/"
[[ -d static ]] && cp -R static "$BACKEND_DIR/"
[[ -d templates ]] && cp -R templates "$BACKEND_DIR/"
[[ -f .env ]] && cp .env "$BACKEND_DIR/"

echo "[desktop-runtime] Backend runtime is ready: $BACKEND_DIR"
echo "[desktop-runtime] Next: cd frontend && npm run desktop:pack"
