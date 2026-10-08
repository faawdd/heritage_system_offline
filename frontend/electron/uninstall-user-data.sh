#!/bin/sh
set -eu

APP_DATA_NAME='heritage-frontend'

remove_user_data() {
  user_home=$1
  [ -n "$user_home" ] || return 0
  rm -rf "$user_home/.config/$APP_DATA_NAME"
  rm -rf "$user_home/.cache/$APP_DATA_NAME"
  rm -rf "$user_home/.local/share/$APP_DATA_NAME"
  rm -rf "$user_home/.heritage-system"
  rm -rf "$user_home/Library/Application Support/$APP_DATA_NAME"
  rm -rf "$user_home/Library/Caches/$APP_DATA_NAME"
}

case "${1:-}" in
  remove|purge|0)
    for user_home in /root /home/*; do
      [ -d "$user_home" ] && remove_user_data "$user_home"
    done
    exit 0
    ;;
  upgrade|1)
    exit 0
    ;;
  --confirm)
    printf 'This permanently deletes this application\047s local database, uploads, backups, logs, and settings.\n'
    printf 'Type DELETE to continue: '
    IFS= read -r confirmation
    [ "$confirmation" = 'DELETE' ] || exit 1
    remove_user_data "${HOME:-}"
    exit 0
    ;;
  *)
    printf 'Run with --confirm to remove this user\047s data before deleting the application.\n' >&2
    exit 2
    ;;
esac