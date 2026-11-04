#!/usr/bin/env bash
# Platform firewall: CTFd's nginx (80/443) answers ONLY Cloudflare. Safe to re-run.
#   sudo ./scripts/harden-platform.sh            # install + apply + self-check
#   sudo ctf-platform-firewall status|remove     # afterwards
# Why: Docker-published ports skip ufw. Without this, anyone with the server IP skips Cloudflare
# (no DDoS protection, no WAF, fake client IPs). Rules live in Docker's DOCKER-USER chain and are
# re-applied by a systemd unit whenever Docker (re)starts. Also drops any OTHER port a container
# publishes by mistake (3306, 6379, 8000...).
# Run harden-base.sh first (ufw blocks the same ports for IPv6 / docker-proxy).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
HERE=$(cd "$(dirname "$0")" && pwd)

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
[[ -n $IFACE ]] || { echo "No default route interface found"; exit 1; }

echo "[1/3] Install rules (interface $IFACE)"
cat > /etc/default/ctf-platform-firewall <<EOF
IFACE=$IFACE
PORTS=80,443
# https://www.cloudflare.com/ips-v4 (re-check before each event: sudo ctf-platform-firewall status)
CF_V4="173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22"
# extra sources allowed on 80/443 (comma list), e.g. for a test without Cloudflare. Normally empty.
EXTRA=
EOF
cat > /usr/local/sbin/ctf-platform-firewall <<'EOF'
#!/usr/bin/env bash
# ctf-platform-firewall apply|remove|status   (config: /etc/default/ctf-platform-firewall)
set -euo pipefail
. /etc/default/ctf-platform-firewall
ipt() { iptables -w "$@"; }
C=CTF-PLATFORM
remove() {
  while ipt -D DOCKER-USER -j $C 2>/dev/null; do :; done
  ipt -F $C 2>/dev/null || true; ipt -X $C 2>/dev/null || true
}
apply() {
  ipt -N DOCKER-USER 2>/dev/null || true
  remove
  ipt -N $C
  ipt -A $C ! -i "$IFACE" -j RETURN                                          # container -> out, container <-> container
  ipt -A $C -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN             # replies
  for src in $CF_V4 ${EXTRA//,/ }; do
    ipt -A $C -p tcp -s "$src" -m conntrack --ctorigdstport 80 --ctdir ORIGINAL -j RETURN
    ipt -A $C -p tcp -s "$src" -m conntrack --ctorigdstport 443 --ctdir ORIGINAL -j RETURN
  done
  ipt -A $C -j DROP                                                          # everything else from outside
  ipt -I DOCKER-USER 1 -j $C
}
case ${1:-status} in
  apply)  apply;  echo "ctf-platform-firewall: applied ($(ipt -S $C | grep -c RETURN) allow rules)";;
  remove) remove; echo "ctf-platform-firewall: removed";;
  status) ipt -S DOCKER-USER | grep -q -- "-j $C" && echo "ctf-platform-firewall: ACTIVE" || echo "ctf-platform-firewall: NOT active"
          ipt -L $C -n -v 2>/dev/null | awk 'NR<=2 || /DROP/' ;;
  *) echo "usage: $0 apply|remove|status"; exit 1;;
esac
EOF
chmod 755 /usr/local/sbin/ctf-platform-firewall
cat > /etc/systemd/system/ctf-platform-firewall.service <<'EOF'
[Unit]
Description=CTF platform firewall (80/443 only from Cloudflare)
After=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/ctf-platform-firewall apply
ExecStop=/usr/local/sbin/ctf-platform-firewall remove

[Install]
WantedBy=multi-user.target docker.service
EOF
systemctl daemon-reload
systemctl enable -q ctf-platform-firewall
systemctl restart ctf-platform-firewall

echo "[2/3] Status"
ctf-platform-firewall status | sed 's/^/      /'
command -v ufw >/dev/null && ufw status | grep -q "Status: active" || echo "      !! ufw not active: run harden-base.sh too"

echo "[3/3] Self-check (through Cloudflare)"
SITE=$(grep -h '^SITE_URL=' /etc/default/ctf-alert /etc/default/ctf-live 2>/dev/null | grep https | head -1 | cut -d= -f2-)
if [[ -n $SITE ]]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$SITE" || true)
  if [[ $code =~ ^(200|301|302|303)$ ]]; then echo "      $SITE -> $code  OK"
  else echo "      !! $SITE -> ${code:-no answer}. Undo: sudo ctf-platform-firewall remove"; exit 1; fi
else
  echo "      (no https SITE_URL in /etc/default/ctf-alert, open the site in a browser)"
fi
echo
echo "Check from your laptop: http://<server-ip>  must time out;  https://internal.ctfc.live  must work."
