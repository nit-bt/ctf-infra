#!/usr/bin/env bash
# Base hardening for every Contabo server (platform and challenge). Safe to re-run.
#   sudo ./scripts/harden-base.sh
# Run AFTER setup-users.sh harden-ssh (key-only SSH works). Does:
#   1. ufw: deny incoming except SSH (+ Docker API 2376 from the platform on challenge servers)
#   2. fail2ban for SSH
#   3. automatic security updates (unattended-upgrades), reboot at 04:00 if a kernel update needs it
#   4. Copy Fail (CVE-2026-31431) mitigation: algif_aead module off (nothing of ours uses it)
# Docker-published ports (CTFd's nginx, challenge instances) skip ufw: harden-platform.sh and
# CTFd-Docker-Challenges/firewall/harden-chal-host.sh handle those.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi

echo "[1/4] Firewall (ufw)"
apt-get install -y -qq ufw >/dev/null
ufw allow 22/tcp comment 'SSH' >/dev/null
CHAL_CONF=/etc/default/ctf-docker-firewall          # written by harden-chal-host.sh
if [[ -f $CHAL_CONF ]]; then
  PLATFORM_IP=$(. "$CHAL_CONF"; echo "${PLATFORM_IP:-}")
  for ip in ${PLATFORM_IP//,/ }; do
    ufw allow from "$ip" to any port 2376 proto tcp comment 'Docker API from platform' >/dev/null
    echo "      2376 allowed from $ip"
  done
fi
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw --force enable >/dev/null
ufw status | sed 's/^/      /'

echo "[2/4] fail2ban (SSH)"
apt-get install -y -qq fail2ban >/dev/null
cat > /etc/fail2ban/jail.d/ctf.conf <<'EOF'
[sshd]
enabled  = true
backend  = systemd
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
systemctl enable -q --now fail2ban
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd | grep -E "Currently banned|Total failed" | sed 's/^/      /' || true

echo "[3/4] Automatic security updates"
apt-get install -y -qq unattended-upgrades >/dev/null
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat > /etc/apt/apt.conf.d/52ctf-unattended <<'EOF'
// security updates only (Ubuntu default origins) + reboot at 04:00 when a kernel update needs it.
// Event day: sudo systemctl stop unattended-upgrades apt-daily.timer apt-daily-upgrade.timer
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
systemctl enable -q --now unattended-upgrades
echo "      on (security only, reboot 04:00 if needed)"

echo "[4/4] Copy Fail mitigation"
echo "install algif_aead /bin/false" > /etc/modprobe.d/ctf-copyfail.conf
modprobe -r algif_aead 2>/dev/null || true
if lsmod | grep -q '^algif_aead'; then echo "      !! algif_aead still loaded: reboot"; else echo "      algif_aead off"; fi

echo
echo "Done. Test a NEW SSH login before closing this one."
