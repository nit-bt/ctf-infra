#!/usr/bin/env bash
# Back up CTFd: database dump + uploaded files + secret key -> one .tar.gz
#
#   sudo ./scripts/backup-ctfd.sh [ctfd-dir] [backup-dir]
#   defaults: /opt/ctf/CTFd   /opt/ctf/backups
#
# Keeps the newest 14 backups here. A backup on the same disk dies with the server, so:
# if /etc/default/ctfd-backup sets OFFSITE, each backup is also pushed to the spare server
# (see docs/failover.md). Exit code 2 = backup saved here but the push failed.
#
# Normal days, 03:15:       15 3 * * *     /opt/ctf/ctf-infra/scripts/backup-ctfd.sh
# Event day, every 15 min:  */15 8-18 * * * /opt/ctf/ctf-infra/scripts/backup-ctfd.sh >> /var/log/ctfd-backup.log 2>&1
set -euo pipefail

CTFD_DIR=${1:-/opt/ctf/CTFd}
OUT_DIR=${2:-/opt/ctf/backups}
KEEP=14
OFFSITE=""                      # e.g. ctfbackup@34.1.2.3:   (set in /etc/default/ctfd-backup)
OFFSITE_KEY=/root/.ssh/ctfd-backup
[[ -f /etc/default/ctfd-backup ]] && . /etc/default/ctfd-backup

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

if [[ -n $OFFSITE ]]; then
  echo "[+] Push to spare: $OFFSITE"
  if rsync -t --timeout=60 -e "ssh -i $OFFSITE_KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15" \
       "$FILE" "$OFFSITE"; then
    date +%s > "$OUT_DIR/.last-offsite-ok"
    echo "Pushed."
  else
    echo "PUSH FAILED - backup is only on this server"; exit 2
  fi
else
  echo "No OFFSITE set - copy it off by hand:  scp <user>@<server-ip>:$FILE ."
fi
