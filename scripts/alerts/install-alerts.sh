#!/usr/bin/env bash
# Install ctf-alert on a server.
#
#   sudo ./scripts/alerts/install-alerts.sh platform     # on the CTFd server
#   sudo ./scripts/alerts/install-alerts.sh chal         # on each challenge server
#
# Then: sudo nano /etc/default/ctf-alert   (Telegram and/or Discord + PEERS)
#       sudo ctf-alert test                (phone should buzz)
#       sudo systemctl enable --now ctf-alert.timer
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
ROLE=${1:-}
[[ $ROLE == platform || $ROLE == chal ]] || { echo "Usage: sudo $0 platform|chal"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)

install -m 0755 "$HERE/ctf-alert" /usr/local/sbin/ctf-alert

if [[ ! -f /etc/default/ctf-alert ]]; then
    cat > /etc/default/ctf-alert <<EOF
# ctf-alert config ($(date +%F))
ROLE=$ROLE
NAME=$(hostname)

# --- where alerts go (fill one or both) ---
# Telegram: talk to @BotFather -> /newbot -> copy the token.
#           Send your bot any message, then open
#           https://api.telegram.org/bot<TOKEN>/getUpdates  and copy "chat":{"id": ...}
TG_BOT_TOKEN=
TG_CHAT_ID=
# Discord: channel -> Edit Channel -> Integrations -> Webhooks -> New Webhook -> Copy URL
DISCORD_WEBHOOK=

# --- other servers to watch (name=ip:port, space separated) ---
# platform: each challenge server's Docker API, e.g.  "chal-1=<chal-1-ip>:2376 chal-2=<chal-2-ip>:2376"
# chal:     the platform's web port,               e.g.  "platform=<platform-ip>:80"
PEERS=""

SITE_URL=http://localhost
RAM_WARN=85
DISK_WARN=85
REMIND_MIN=15
EOF
    chmod 600 /etc/default/ctf-alert
    echo "Created /etc/default/ctf-alert"
else
    echo "/etc/default/ctf-alert already exists, left as is"
fi

cat > /etc/systemd/system/ctf-alert.service <<'EOF'
[Unit]
Description=CTF alert checks
After=network-online.target docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ctf-alert run
EOF

cat > /etc/systemd/system/ctf-alert.timer <<'EOF'
[Unit]
Description=Run CTF alert checks every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
echo
echo "Installed. Next:"
echo "  1. sudo nano /etc/default/ctf-alert      # Telegram and/or Discord, PEERS"
echo "  2. sudo ctf-alert status                 # see what it checks right now"
echo "  3. sudo ctf-alert test                   # your phone should get a message"
echo "  4. sudo systemctl enable --now ctf-alert.timer"
