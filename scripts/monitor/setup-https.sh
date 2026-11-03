#!/usr/bin/env bash
# HTTPS for the monitor VM: kuma.<domain> -> Uptime Kuma (:3001), live.<domain> -> live board (:3002).
#   sudo ./scripts/monitor/setup-https.sh ctfc.live
# Needs first: Cloudflare DNS  kuma.<domain> and live.<domain>  A -> this VM's public IP (orange cloud),
#              Cloudflare SSL/TLS mode "Full (strict)", and ports 80 + 443 open to this VM.
# Caddy gets real certificates by itself (Let's Encrypt) and renews them.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
DOMAIN=${1:-}
[[ $DOMAIN =~ ^[a-z0-9.-]+\.[a-z]{2,}$ ]] || { echo "Usage: sudo $0 <domain>   e.g. ctfc.live"; exit 1; }

command -v caddy >/dev/null || { apt-get update -qq && apt-get install -y -qq caddy; }

cat > /etc/caddy/Caddyfile <<CADDY
# managed by ctf-infra scripts/monitor/setup-https.sh
kuma.$DOMAIN {
	reverse_proxy localhost:3001
}

live.$DOMAIN {
	reverse_proxy localhost:3002 {
		flush_interval -1      # live updates (server-sent events) go straight through
	}
}
CADDY
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl enable caddy >/dev/null 2>&1 || true
systemctl reload caddy || systemctl restart caddy

echo "Done. In ~1 minute (first certificates):"
echo "  https://kuma.$DOMAIN"
echo "  https://live.$DOMAIN"
echo "Then close 3001/3002 to the internet (docs/domain.md, step 5)."
