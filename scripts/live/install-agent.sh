#!/usr/bin/env bash
# Install the ctf-live agent on a platform or challenge server.
#   sudo ./scripts/live/install-agent.sh platform|chal
# Then put LIVE_URL + LIVE_TOKEN in /etc/default/ctf-live and: sudo systemctl restart ctf-live-agent
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
ROLE=${1:-}
[[ $ROLE == platform || $ROLE == chal ]] || { echo "Usage: sudo $0 platform|chal"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)

install -m 755 "$HERE/agent.py" /usr/local/sbin/ctf-live-agent

CONF=/etc/default/ctf-live
if [[ ! -f $CONF ]]; then
  cat > $CONF <<CFG
# ctf-live agent: sends live stats to the board every INTERVAL seconds (docs/monitoring.md)
LIVE_URL=http://<monitor-ip>:3002
LIVE_TOKEN=
NAME=$(hostname)
ROLE=$ROLE
INTERVAL=2
SITE_URL=http://localhost
CFG
  chmod 600 $CONF
  echo "Created $CONF: fill in LIVE_URL and LIVE_TOKEN"
fi

cat > /etc/systemd/system/ctf-live-agent.service <<'UNIT'
[Unit]
Description=CTFC live board agent
After=network-online.target docker.service

[Service]
ExecStart=/usr/bin/python3 /usr/local/sbin/ctf-live-agent
Restart=always
RestartSec=5
Nice=10

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ctf-live-agent >/dev/null
if grep -q '^LIVE_TOKEN=.\+' $CONF && ! grep -q '<monitor-ip>' $CONF; then
  systemctl restart ctf-live-agent && echo "Agent running (sudo systemctl status ctf-live-agent)"
else
  echo "Fill in $CONF, then: sudo systemctl restart ctf-live-agent"
fi
