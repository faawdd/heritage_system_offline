#!/usr/bin/env bash
set -euo pipefail

APP_NAME_DEFAULT="基层文物管理系统（离线版）.app"
APP_PATH="${1:-/Applications/${APP_NAME_DEFAULT}}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "[fix] App bundle not found: $APP_PATH" >&2
  echo "[fix] Usage: ./scripts/macos_fix_damaged_app.sh /Applications/YourApp.app" >&2
  exit 1
fi

echo "[fix] Target app: $APP_PATH"

echo "[fix] Removing quarantine attribute..."
xattr -rd com.apple.quarantine "$APP_PATH" || true

echo "[fix] Re-signing app bundle with ad-hoc identity..."
codesign --force --deep --sign - "$APP_PATH"

echo "[fix] Verifying code signature..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "[fix] Gatekeeper assessment..."
spctl --assess --type execute --verbose=2 "$APP_PATH" || true

echo "[done] Fix finished. Try opening the app again."
