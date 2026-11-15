#!/usr/bin/env bash
# Create the first admin account (or reset an existing admin's password). Asks for the password itself;
# nothing is stored in shell history or in a file.
#   sudo ./deploy/init-admin.sh <admin-login> [--name "Display name"]
# Run it once after install. Demo accounts are never created on a server.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo 'Run with sudo.' >&2; exit 1; fi
if [[ $# -lt 1 ]]; then echo "Usage: sudo $0 <admin-login> [--name \"Display name\"]" >&2; exit 1; fi
APP=/opt/scoilmate
ENV_FILE=/etc/scoilmate/scoilmate.env
[[ -x $APP/.venv/bin/python && -f $ENV_FILE ]] || { echo 'ScoilMate is not installed here; run deploy/install-ubuntu.sh first.' >&2; exit 1; }
# Run as the app user with the same environment as the service; the password prompt reads from this terminal.
cd "$APP"
exec sudo --preserve-env=TERM -u scoilmate bash -c \
  'set -a; . "$1"; set +a; exec "$2" -m scoilmate.cli create-admin "${@:3}"' _ "$ENV_FILE" "$APP/.venv/bin/python" "$@"
