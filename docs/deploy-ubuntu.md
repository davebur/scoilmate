# Deploying ScoilMate on Ubuntu (uvicorn + nginx)

This is for a small server with a domain name and HTTPS. It is **not** yet approved for real students: complete the open items in [docs/07](07-backlog-and-acceptance.md) (privacy/DPIA, notices, teacher and Gaeilge review) first.

## What you get
- `/opt/scoilmate`: the code and its own Python virtual environment (`.venv`)
- `/var/lib/scoilmate`: the SQLite database and backups (the only writable place for the app)
- `/etc/scoilmate/scoilmate.env`: settings (secure cookies on, draft practice off)
- `scoilmate.service`: uvicorn on `127.0.0.1:8000`, runs migrations and content import before starting
- nginx on ports 80/443: HTTPS, redirect from HTTP, proxy to uvicorn, login brake

## Before you start
1. A server running Ubuntu 22.04 or 24.04, with `sudo` access.
2. A DNS `A`/`AAAA` record for your domain pointing at the server.
3. Ports 80 and 443 open to the internet; nothing else needed.
4. A checkout of this repository on the server (`git clone ...`). Run the commands below from that checkout.

## Install
```sh
cd /path/to/scoilmate
sudo DOMAIN=scoilmate.example.ie ./deploy/install-ubuntu.sh
```
The script installs packages, creates the `scoilmate` system user, copies the code, builds the venv from `requirements.txt`, runs migrations and imports the content file, then installs and starts the service and the nginx site. It is safe to re-run: existing settings are kept and any changed nginx config is backed up first.

If the certificate is not there yet, the script stops short of enabling HTTPS and prints the commands. Then:
```sh
sudo certbot certonly --nginx -d scoilmate.example.ie
sudo nginx -t && sudo systemctl reload nginx
```

## Create the first admin (no demo accounts on a server)
```sh
sudo /opt/scoilmate/deploy/init-admin.sh your-login --name "Your Name"
```
You're asked for the password twice; it isn't stored anywhere. Run it again with the same login to reset that admin's password. Parents and students are then created from the admin pages.

## Check it is working
```sh
systemctl status scoilmate
journalctl -u scoilmate -n 50
curl -fsS http://127.0.0.1:8000/health      # on the server: uvicorn directly
curl -fsSI https://scoilmate.example.ie/     # from anywhere: through nginx
```
Expected: `{"status":"ok",...}` from `/health`, and `HTTP/2 200` from the public URL.

## Settings
Edit `/etc/scoilmate/scoilmate.env`, then `sudo systemctl restart scoilmate`.

| Setting | Server value | Meaning |
|---|---|---|
| `SCOILMATE_DB` | `/var/lib/scoilmate/scoilmate.db` | database file |
| `SCOILMATE_SECURE_COOKIES` | `1` | Secure and `__Host-` cookies; needs HTTPS |
| `SCOILMATE_ALLOW_DRAFT_PRACTICE` | `0` | students see only published content |

## Backups
Run as the app user so the file ends up owned correctly:
```sh
sudo -u scoilmate bash -c 'set -a; . /etc/scoilmate/scoilmate.env; set +a; cd /opt/scoilmate && .venv/bin/python -m scoilmate.cli backup --out /var/lib/scoilmate/backups/scoilmate-$(date +%F).db'
```
Restore only with the service stopped:
```sh
sudo systemctl stop scoilmate
sudo -u scoilmate bash -c 'set -a; . /etc/scoilmate/scoilmate.env; set +a; cd /opt/scoilmate && .venv/bin/python -m scoilmate.cli restore /var/lib/scoilmate/backups/FILE.db --yes'
sudo systemctl start scoilmate
``` Copy backups off the server too. Backups hold student progress: treat them as personal data.

## Updating
```sh
cd /path/to/scoilmate && git pull
sudo DOMAIN=scoilmate.example.ie ./deploy/install-ubuntu.sh
```
Migrations run automatically on restart. Take a backup first.

## Troubleshooting
- **Login refused:** check `journalctl -u scoilmate`. Repeated failures lock the account for 15 minutes.
- **502 Bad Gateway from nginx:** the service isn't running. `systemctl status scoilmate`.
- **Cookies not kept:** the site must be reached over HTTPS, since secure cookies are on.
- **Every visitor appears to share one IP in logs:** nginx must be the only thing reaching port 8000; the unit binds to 127.0.0.1, so keep it that way.

## Known limits
- One uvicorn worker, by design: login rate limits are held in memory per process.
- SQLite suits a small pilot (tens of concurrent users). Revisit before growing.
- No automatic backups yet: schedule one (cron or a systemd timer) and copy it off-server.
- Not verified on a real Ubuntu host from this workspace (no root access or nginx here). The scripts pass `bash -n` and the unit passes `systemd-analyze verify` apart from the missing installed paths. Test on a staging server first.
