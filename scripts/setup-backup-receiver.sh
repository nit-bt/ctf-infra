#!/usr/bin/env bash
# Run on the SPARE platform (GCP). Lets the live platform push backups here, and nothing else.
#
#   sudo ./scripts/setup-backup-receiver.sh "<public key from the live platform>"
#
# Creates user 'ctfbackup' with no password and no shell access: its one SSH key may only
# rsync files INTO /srv/ctfd-backups (write-only, can't read or delete what's there).
# Keeps the newest 200 backups (about 2 days at one every 15 min).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
KEY=${1:-}
if ! [[ $KEY =~ ^ssh-(ed25519|rsa)\  ]]; then
  echo "Usage: sudo $0 \"ssh-ed25519 AAAA... root@platform\""
  echo "(get it on the live platform with: sudo cat /root/.ssh/ctfd-backup.pub)"; exit 1
fi

DIR=/srv/ctfd-backups
command -v rsync >/dev/null || apt-get install -y -qq rsync
RRSYNC=$(command -v rrsync || echo /usr/share/doc/rsync/scripts/rrsync)
[[ -x $RRSYNC ]] || { echo "rrsync not found (comes with the rsync package)"; exit 1; }

id ctfbackup >/dev/null 2>&1 || useradd --system --home-dir "$DIR" --shell /bin/sh ctfbackup
mkdir -p "$DIR/.ssh"
echo "restrict,command=\"$RRSYNC -wo $DIR\" $KEY" > "$DIR/.ssh/authorized_keys"
chown -R ctfbackup:ctfbackup "$DIR"; chmod 750 "$DIR"; chmod 700 "$DIR/.ssh"; chmod 600 "$DIR/.ssh/authorized_keys"

# prune old backups every hour
cat > /etc/cron.d/ctfd-backup-prune <<EOF
17 * * * * root ls -1t $DIR/ctfd-*.tar.gz 2>/dev/null | tail -n +201 | xargs -r rm -f
EOF

echo "Ready. Backups will land in $DIR"
echo "Firewall: allow TCP 22 from the live platform's public IP only (GCP: VPC firewall rule)."
