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

CONF=/etc/default/ctf-live-board
if [[ ! -f $CONF ]]; then
  cat > $CONF <<CFG
PORT=3002
LIVE_TOKEN=$(openssl rand -hex 24)
LIVE_USER=admin
LIVE_PASS=$(openssl rand -base64 12 | tr -d '/+=')
CFG
  chmod 600 $CONF
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

. $CONF
IP=$(curl -s --max-time 3 -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || hostname -I | awk '{print $1}')
echo
echo "Board running.  Page:  http://$IP:$PORT   login: $LIVE_USER / $LIVE_PASS"
echo "Agents need:   LIVE_URL=http://<this VM's IP>:$PORT   LIVE_TOKEN=$LIVE_TOKEN"
echo "Firewall: allow TCP $PORT (GCP: add it to the 'kuma' rule, or a new rule with the same tag)."
