#!/usr/bin/env bash
# Install ScoilMate on Ubuntu (22.04/24.04): app user, code in /opt/scoilmate, venv, database, systemd and nginx.
# Run from a checkout of this repository, as root:
#   sudo DOMAIN=scoilmate.example.ie ./deploy/install-ubuntu.sh
# Safe to re-run: keeps existing env/config (backs up changed nginx config), and re-applies code and migrations.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo 'Run with sudo.' >&2; exit 1; fi
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
APP=/opt/scoilmate
DATA=/var/lib/scoilmate
ENV_DIR=/etc/scoilmate
ENV_FILE=$ENV_DIR/scoilmate.env
DOMAIN="${DOMAIN:-}"
[[ -n $DOMAIN ]] || { echo 'Set DOMAIN, e.g. sudo DOMAIN=scoilmate.example.ie ./deploy/install-ubuntu.sh' >&2; exit 1; }
[[ -f $REPO/scoilmate/app.py && -f $REPO/requirements.txt ]] || { echo "Not a ScoilMate checkout: $REPO" >&2; exit 1; }

echo '==> System packages'
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx rsync

echo '==> App user and directories'
id scoilmate >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin scoilmate
install -d -o root -g root -m 0755 "$APP"
install -d -o scoilmate -g scoilmate -m 0750 "$DATA" "$DATA/backups"
install -d -o root -g scoilmate -m 0750 "$ENV_DIR"

echo '==> Copy code (keeps the venv, database and backups)'
rsync -a --delete \
  --exclude '.git/' --exclude '.venv/' --exclude 'instance/' --exclude '__pycache__/' --exclude '*.pyc' \
  "$REPO"/ "$APP"/
chown -R root:root "$APP"

echo '==> Python environment (project venv only)'
[[ -x $APP/.venv/bin/python ]] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/python" -m pip install --quiet --upgrade pip
"$APP/.venv/bin/python" -m pip install --quiet -r "$APP/requirements.txt"

echo '==> Settings'
if [[ ! -f $ENV_FILE ]]; then
  install -m 0640 -o root -g scoilmate "$REPO/deploy/scoilmate.env.example" "$ENV_FILE"
  echo "Created $ENV_FILE from the example (secure cookies on, draft practice off)."
else
  echo "Kept existing $ENV_FILE (compare with deploy/scoilmate.env.example if unsure)."
fi

echo '==> Database: migrate and import reviewed content'
sudo_app() { sudo -u scoilmate bash -c 'set -a; . "$1"; set +a; cd "$2"; shift 2; exec "$@"' _ "$ENV_FILE" "$APP" "$@"; }
sudo_app "$APP/.venv/bin/python" -m scoilmate.cli migrate
sudo_app "$APP/.venv/bin/python" -m scoilmate.cli import-content

echo '==> systemd service'
install -m 0644 "$APP/deploy/scoilmate.service" /etc/systemd/system/scoilmate.service
systemctl daemon-reload
systemctl enable --now scoilmate.service

echo '==> nginx reverse proxy'
install -d /etc/nginx/snippets
install -m 0644 "$APP/deploy/scoilmate-proxy.conf" /etc/nginx/snippets/scoilmate-proxy.conf
SITE=/etc/nginx/sites-available/scoilmate.conf
sed "s/scoilmate.example.ie/$DOMAIN/g" "$APP/deploy/nginx.conf" > "$SITE.new"
if [[ -f $SITE ]] && ! cmp -s "$SITE" "$SITE.new"; then
  cp "$SITE" "$SITE.bak.$(date +%Y%m%d%H%M%S)"
  echo "Previous nginx site backed up."
fi
mv "$SITE.new" "$SITE"
ln -sf "$SITE" /etc/nginx/sites-enabled/scoilmate.conf

if [[ -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]]; then
  nginx -t && systemctl reload nginx
  echo "nginx reloaded for https://$DOMAIN/"
else
  echo "No certificate yet for $DOMAIN. Obtain one, then reload nginx:"
  echo "  sudo certbot certonly --nginx -d $DOMAIN   # needs DNS for $DOMAIN pointing at this server"
  echo "  sudo nginx -t && sudo systemctl reload nginx"
fi

cat <<MSG

Installed. Next:
  1. Create the first admin:   sudo $APP/deploy/init-admin.sh <admin-login>
     (or from the repo: sudo ./deploy/init-admin.sh <admin-login>)
  2. Check the service:        systemctl status scoilmate ; journalctl -u scoilmate -n 50
  3. Open https://$DOMAIN/
MSG
