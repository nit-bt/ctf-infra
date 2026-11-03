#!/usr/bin/env bash
# Install the ctf-live board on the monitor VM (next to Uptime Kuma).
#   sudo ./scripts/live/install-board.sh
# Prints the page URL, login, and the token the agents need. Safe to re-run (keeps token + password).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
HERE=$(cd "$(dirname "$0")" && pwd)
command -v python3 >/dev/null || apt-get install -y -qq python3

install -d -m 755 /opt/ctf-live
install -m 755 "$HERE/board.py" /opt/ctf-live/board.py
install -m 644 "$HERE/index.html" /opt/ctf-live/index.html
install -m 644 "$HERE/login.html" /opt/ctf-live/login.html

# password changer: sudo ctf-live-passwd
cat > /usr/local/sbin/ctf-live-passwd <<'SH'
#!/bin/sh
python3 /opt/ctf-live/board.py --set-password && systemctl restart ctf-live-board && echo "Board restarted: everyone has to log in again."
SH
chmod 755 /usr/local/sbin/ctf-live-passwd

CONF=/etc/default/ctf-live-board
NEWPASS=""
if [[ ! -f $CONF ]]; then
  NEWPASS=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)
  cat > $CONF <<CFG
PORT=3002
LIVE_TOKEN=$(openssl rand -hex 24)
LIVE_USER=admin
LIVE_PASS_HASH=$(printf '%s\n' "$NEWPASS" | python3 /opt/ctf-live/board.py --hash)
CFG
  chmod 600 $CONF
elif grep -q '^LIVE_PASS=' $CONF && ! grep -q '^LIVE_PASS_HASH=' $CONF; then
  # upgrade an old plain-text password to a hash (same password keeps working)
  OLD=$(sed -n 's/^LIVE_PASS=//p' $CONF | tr -d "\"'")
  H=$(printf '%s\n' "$OLD" | python3 /opt/ctf-live/board.py --hash)
  sed -i '/^LIVE_PASS=/d' $CONF && echo "LIVE_PASS_HASH=$H" >> $CONF
  echo "Upgraded the board password to a hash (same password)."
fi

id ctflive >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin ctflive
chown ctflive $CONF

cat > /etc/systemd/system/ctf-live-board.service <<'UNIT'
[Unit]
Description=CTFC live board
After=network-online.target

[Service]
User=ctflive
ExecStart=/usr/bin/python3 /opt/ctf-live/board.py
Restart=always
RestartSec=2
StateDirectory=ctf-live
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now ctf-live-board
systemctl restart ctf-live-board

PORT=$(sed -n 's/^PORT=//p' $CONF); USERN=$(sed -n 's/^LIVE_USER=//p' $CONF)
echo
echo "Board running on port ${PORT:-3002}. Open it via https://live.<domain> (docs/domain.md) or http://<this VM's IP>:${PORT:-3002}"
if [[ -n $NEWPASS ]]; then
  echo "Login: ${USERN:-admin} / $NEWPASS     <- shown ONCE, only its hash is stored. Save it now."
else
  echo "Login: ${USERN:-admin} / (unchanged)  Change it: sudo ctf-live-passwd"
fi
echo "Agent token: sudo grep LIVE_TOKEN $CONF   (the Servers tab puts it in the install command for you)"
