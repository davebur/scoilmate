#!/usr/bin/env bash
# Update an installed ScoilMate (/opt/scoilmate) from a pulled checkout, without touching live data or SSL.
#
#   cd /path/to/checkout && git pull
#   sudo ./deploy/update-ubuntu.sh
#
# NEVER changed by this script:
#   - nginx site, snippets and certificates (/etc/nginx, /etc/letsencrypt)
#   - /etc/scoilmate/scoilmate.env (settings, secrets)
#   - /var/lib/scoilmate (the live database and backups)
#   - /opt/scoilmate/.venv is updated in place, never replaced
#
# Steps: pre-flight checks -> backup the database -> keep the old code for rollback -> copy new code
#        -> pip install -> stop service -> migrate + import content -> start -> health check.
# On any failure after the backup: stop the service, restore the old code and (if migrated) the
# database backup, start the service again, and exit non-zero. Nothing is left half-updated.
#
# Options: ALLOW_DIRTY=1 to update from a checkout with uncommitted changes.
set -euo pipefail

APP="${APP:-/opt/scoilmate}"
DATA="${DATA:-/var/lib/scoilmate}"
ENV_FILE="${ENV_FILE:-/etc/scoilmate/scoilmate.env}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"
PREV="$APP.prev"
BACKUP="$DATA/backups/pre-update-$TS.db"
STATE=0 # 0 = nothing changed yet, 1 = code changed, 2 = database migrated
OLD_UNIT_SAVED=0

die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
[[ -f $REPO/scoilmate/app.py && -f $REPO/requirements.txt ]] || die "not a ScoilMate checkout: $REPO"
[[ $REPO != "$APP" ]] || die "run this from your checkout, not from $APP"
[[ -x $APP/.venv/bin/python && -f $ENV_FILE ]] || die "not installed here; run deploy/install-ubuntu.sh first"
[[ -d $DATA ]] || die "$DATA missing"

# ---- helpers ----
run_app() { # run a command as the app user with the service's settings
  sudo -u scoilmate bash -c 'set -a; . "$1"; set +a; cd "$2"; shift 2; exec "$@"' _ \
    "$ENV_FILE" "$APP" "$@"
}
sync_code() { # $1 = source dir, $2 = destination dir (keeps .venv and live instance data)
  rsync -a --delete \
    --exclude '.git/' --exclude '.venv/' --exclude 'instance/' --exclude '__pycache__/' \
    --exclude '*.pyc' --exclude '*.prev' \
    "$1"/ "$2"/
}
wait_healthy() {
  for _ in $(seq 1 30); do
    if curl -fsS "$HEALTH_URL" 2>/dev/null | grep -q '"status":"ok"'; then return 0; fi
    sleep 1
  done
  return 1
}
rollback() {
  local rc=$?
  trap - ERR
  echo "!! Update failed (exit $rc). Rolling back." >&2
  systemctl stop scoilmate || true
  if [[ $STATE -ge 2 && -f $BACKUP ]]; then
    echo "   restoring database from $BACKUP" >&2
    run_app "$APP/.venv/bin/python" -m scoilmate.cli restore "$BACKUP" --yes || echo "   DATABASE RESTORE FAILED: restore manually from $BACKUP" >&2
  fi
  if [[ $STATE -ge 1 && -d $PREV ]]; then
    echo "   restoring previous code from $PREV" >&2
    sync_code "$PREV" "$APP"
    chown -R root:root "$APP"
    if [[ $OLD_UNIT_SAVED -eq 1 ]]; then
      install -m 0644 "$PREV/scoilmate.service.old" /etc/systemd/system/scoilmate.service
      systemctl daemon-reload
    fi
  fi
  systemctl start scoilmate || true
  if wait_healthy; then echo "   rolled back; the previous version is serving again." >&2
  else echo "   rollback started but health check still fails: see journalctl -u scoilmate -n 80" >&2; fi
  exit "$rc"
}
trap rollback ERR

# ---- pre-flight ----
echo "==> Pre-flight"
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  echo "    source: $(git -C "$REPO" log -1 --oneline)"
  if [[ -n $(git -C "$REPO" status --porcelain) && ${ALLOW_DIRTY:-0} != 1 ]]; then
    die "checkout has uncommitted changes (commit them, or set ALLOW_DIRTY=1)"
  fi
fi
python3 -m compileall -q "$REPO/scoilmate" >/dev/null || die "new code does not compile"
nginx -t >/dev/null 2>&1 || die "nginx configuration is already failing (nginx -t); fix it first. Nothing was changed."
echo "    nginx config OK (left unchanged by this update)"
systemctl is-active --quiet scoilmate || echo "    note: scoilmate service was not running before the update"

# ---- backup ----
echo "==> Backing up the live database"
install -d -o scoilmate -g scoilmate -m 0750 "$DATA/backups"
run_app "$APP/.venv/bin/python" -m scoilmate.cli backup --out "$BACKUP"
[[ -s $BACKUP ]] || die "backup was not written"
echo "    $BACKUP"

# ---- keep old code for rollback ----
echo "==> Keeping the current code for rollback"
rm -rf "$PREV"
install -d "$PREV"
sync_code "$APP" "$PREV"
cp -f /etc/systemd/system/scoilmate.service "$PREV/scoilmate.service.old" 2>/dev/null && OLD_UNIT_SAVED=1 || true

# ---- new code and packages ----
echo "==> Installing the new code"
STATE=1
sync_code "$REPO" "$APP"
chown -R root:root "$APP"
echo "==> Python packages (project venv)"
"$APP/.venv/bin/python" -m pip install --quiet -r "$APP/requirements.txt"

if ! cmp -s "$REPO/deploy/scoilmate.service" /etc/systemd/system/scoilmate.service 2>/dev/null; then
  echo "==> systemd unit changed: installing it"
  install -m 0644 "$APP/deploy/scoilmate.service" /etc/systemd/system/scoilmate.service
  systemctl daemon-reload
fi

# ---- migrate and restart ----
echo "==> Stopping the service, migrating, importing content"
systemctl stop scoilmate
STATE=2
run_app "$APP/.venv/bin/python" -m scoilmate.cli migrate
run_app "$APP/.venv/bin/python" -m scoilmate.cli import-content
echo "==> Starting the service"
systemctl start scoilmate
wait_healthy || die "service did not become healthy"
trap - ERR
echo "==> Health check passed: $(curl -fsS "$HEALTH_URL")"

# ---- summary ----
cat <<MSG

Update complete.
  Backup of the database taken before the update: $BACKUP
  Previous code kept for rollback in: $PREV
  nginx and SSL: not changed. Check the public site: curl -fsSI https://YOUR-DOMAIN/
  Logs: journalctl -u scoilmate -n 50
MSG
