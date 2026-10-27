#!/usr/bin/env bash
# Restore a backup made by backup-ctfd.sh into this server's CTFd.
#
#   sudo ./scripts/restore-ctfd.sh                       # newest file in /srv/ctfd-backups or /opt/ctf/backups
#   sudo ./scripts/restore-ctfd.sh path/to/ctfd-YYYYMMDD-HHMM.tar.gz
#
# Replaces EVERYTHING in this CTFd (users, solves, challenges, config) with the backup.
# CTFd must already be installed here (docs/03-platform.md) with the same compose setup.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
CTFD_DIR=${CTFD_DIR:-/opt/ctf/CTFd}
FILE=${1:-$(ls -1t /srv/ctfd-backups/ctfd-*.tar.gz /opt/ctf/backups/ctfd-*.tar.gz 2>/dev/null | head -1 || true)}
[[ -f $FILE ]] || { echo "No backup file found. Give a path: sudo $0 <file.tar.gz>"; exit 1; }

echo "Backup : $FILE  ($(du -h "$FILE" | cut -f1), made $(date -r "$FILE" '+%Y-%m-%d %H:%M'))"
echo "Into   : $CTFD_DIR  (this REPLACES all CTFd data here)"
if [[ ${YES:-} != 1 ]]; then read -rp "Type RESTORE to continue: " ok; [[ $ok == RESTORE ]] || { echo "Cancelled"; exit 1; }; fi

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tar xzf "$FILE" -C "$TMP"
[[ -s $TMP/ctfd.sql ]] || { echo "Backup has no database dump, aborting"; exit 1; }

cd "$CTFD_DIR"
echo "[1/4] Stop CTFd (database keeps running)"
docker compose stop ctfd
docker compose up -d db
for i in $(seq 30); do docker compose exec -T db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "select 1"' >/dev/null 2>&1 && break; sleep 2; done

echo "[2/4] Load database"
docker compose exec -T db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"' < "$TMP/ctfd.sql"

echo "[3/4] Uploads + secret key"
if [[ -d $TMP/uploads ]]; then mkdir -p .data/CTFd/uploads && cp -a "$TMP/uploads/." .data/CTFd/uploads/; fi
[[ -f $TMP/.ctfd_secret_key ]] && cp -a "$TMP/.ctfd_secret_key" .

docker compose exec -T cache redis-cli FLUSHALL >/dev/null 2>&1 || true   # old cached config/sessions

echo "[4/4] Start CTFd"
docker compose up -d ctfd
up() { docker compose exec -T ctfd python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=5)" >/dev/null 2>&1; }
for i in $(seq 30); do up && break; sleep 2; done
up && echo "Restored. CTFd is up." || { echo "CTFd not answering yet: sudo docker compose logs --tail 50 ctfd"; exit 1; }
echo "Next: Admin > Docker Config, check every host is UP (docs/failover.md)."
