#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON="$PYTHON_BIN"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

DO_COMMIT=0
DO_PUSH=0
COMMIT_MSG="chore: refresh offline tianditu tiles"

PREFETCH_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      DO_COMMIT=1
      shift
      ;;
    --push)
      DO_PUSH=1
      shift
      ;;
    --commit-message)
      if [[ $# -lt 2 ]]; then
        echo "[tdt-refresh] --commit-message requires a value" >&2
        exit 2
      fi
      COMMIT_MSG="$2"
      shift 2
      ;;
    --help|-h)
      cat <<'EOF'
Usage:
  ./scripts/refresh_tianditu_tiles.sh [options] [-- prefetch_args...]

Options:
  --commit                 Stage tile files and create a git commit if changed.
  --push                   Push current branch after commit (implies --commit).
  --commit-message <msg>   Custom commit message.
  -h, --help               Show help.

Examples:
  ./scripts/refresh_tianditu_tiles.sh
  ./scripts/refresh_tianditu_tiles.sh --commit
  ./scripts/refresh_tianditu_tiles.sh --commit --push
  ./scripts/refresh_tianditu_tiles.sh --commit -- --zoom-min 0 --zoom-max 10

Environment:
  TDT_TK / VITE_TDT_TK     TianDiTu key (optional if default key is accepted)
EOF
      exit 0
      ;;
    --)
      shift
      PREFETCH_ARGS+=("$@")
      break
      ;;
    *)
      PREFETCH_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$DO_PUSH" -eq 1 ]]; then
  DO_COMMIT=1
fi

cd "$PROJECT_ROOT"

echo "[tdt-refresh] python: $PYTHON"
echo "[tdt-refresh] output: $PROJECT_ROOT/static/tiles/tianditu"
"$PYTHON" "$PROJECT_ROOT/scripts/prefetch_tianditu_tiles.py" \
  --output-dir "$PROJECT_ROOT/static/tiles/tianditu" \
  "${PREFETCH_ARGS[@]}"

if [[ "$DO_COMMIT" -eq 0 ]]; then
  echo "[tdt-refresh] done (download only)."
  exit 0
fi

git add static/tiles/tianditu

if git diff --cached --quiet; then
  echo "[tdt-refresh] no tile changes to commit."
  exit 0
fi

git commit -m "$COMMIT_MSG"

echo "[tdt-refresh] commit created."

if [[ "$DO_PUSH" -eq 1 ]]; then
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  git push
  echo "[tdt-refresh] pushed current branch upstream: $current_branch"
fi
