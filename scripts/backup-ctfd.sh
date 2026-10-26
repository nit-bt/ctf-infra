#!/usr/bin/env bash
# Back up CTFd: database dump + uploaded files + secret key -> one .tar.gz
#
#   sudo ./scripts/backup-ctfd.sh [ctfd-dir] [backup-dir]
#   defaults: /opt/ctf/CTFd   /opt/ctf/backups
#
# Keeps the newest 14 backups. Copy them OFF the server (scp) - a backup on
# the same disk dies with the server.
# Daily at 03:15:  sudo crontab -e  ->  15 3 * * * /opt/ctf/ctf-infra/scripts/backup-ctfd.sh
set -euo pipefail

CTFD_DIR=${1:-/opt/ctf/CTFd}
OUT_DIR=${2:-/opt/ctf/backups}
KEEP=14

if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
cd "$CTFD_DIR"

STAMP=$(date +%Y%m%d-%H%M)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT_DIR"

echo "[1/3] Database dump"
docker compose exec -T db sh -c \
  'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --databases ctfd' \
  > "$TMP/ctfd.sql"
[[ -s $TMP/ctfd.sql ]] || { echo "Empty dump, aborting"; exit 1; }

echo "[2/3] Uploads + secret key + config"
[[ -d .data/CTFd/uploads ]] && cp -a .data/CTFd/uploads "$TMP/uploads"
[[ -f .ctfd_secret_key ]] && cp -a .ctfd_secret_key "$TMP/"
cp -a docker-compose.yml "$TMP/"

echo "[3/3] Archive"
FILE="$OUT_DIR/ctfd-$STAMP.tar.gz"
tar czf "$FILE" -C "$TMP" .
chmod 600 "$FILE"
ls -1t "$OUT_DIR"/ctfd-*.tar.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "Saved $FILE ($(du -h "$FILE" | cut -f1))"
echo "Copy off-server:  scp <user>@<server-ip>:$FILE ."
