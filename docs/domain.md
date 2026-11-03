# Domain: ctfc.live

Bought at Namecheap (auto-renew **off**: year 1 is $2.98, renewal is ~$41). DNS runs on **Cloudflare** (free plan):
free HTTPS, hides server IPs, DDoS protection, and switching servers takes seconds (docs/failover.md).

## Names

| Name | Points to | Cloudflare | Used for |
|---|---|---|---|
| `kuma.ctfc.live` | monitor VM | 🟠 Proxied | Uptime Kuma (history, alerts, status page) |
| `live.ctfc.live` | monitor VM | 🟠 Proxied | live board |
| `internal.ctfc.live` | Contabo platform | 🟠 Proxied | the internal CTF site *(when Contabo exists)* |
| `atc.ctfc.live` | ATC platform (Feb) | 🟠 Proxied | the ATC CTF site, later |
| `chal1.ctfc.live` | Contabo challenge server | ⚪ **DNS only** | instance links (`http://chal1.ctfc.live:30123`). Cloudflare can't carry ports 30000-31000 |

## 1. Namecheap → Cloudflare (once)

1. cloudflare.com → sign up → **Add a site** → `ctfc.live` → **Free**.
2. Cloudflare shows 2 nameservers. Namecheap → Domain List → `ctfc.live` → **Manage** → Nameservers → **Custom DNS** → paste both → ✓.
3. Wait for Cloudflare's "active" email (usually < 1 h).
4. Cloudflare → **SSL/TLS** → Overview → mode **Full (strict)**. Edge Certificates → **Always Use HTTPS** on.

## 2. Monitoring names (kuma, live)

DNS records, HTTPS (Caddy + Cloudflare origin certificate) and closing the raw ports for `kuma.ctfc.live` and
`live.ctfc.live`: **[ctfc-monitor](https://github.com/nit-bt/ctfc-monitor)** `docs/https.md`.

## 3. The CTF itself (when Contabo exists)

When the Contabo servers exist (docs/07): add `internal` (🟠) and `chal1` (⚪), set each challenge server's
**Public address** in CTFd Docker Config to `chal1.ctfc.live`. Moving servers is then only a DNS change.

## Origin certificate for the platform

The Cloudflare origin certificate made for the monitor covers `*.ctfc.live`, so `internal.ctfc.live` and `atc.ctfc.live`
can use the same two files (`origin.pem`, `origin.key`) on the platform's nginx: Cloudflare SSL mode stays Full (strict).
