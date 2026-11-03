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

## 2. DNS records for the monitor

Cloudflare → DNS → Records → Add record (twice):

| Type | Name | IPv4 | Proxy |
|---|---|---|---|
| A | `kuma` | monitor VM's **external** IP | 🟠 Proxied |
| A | `live` | monitor VM's **external** IP | 🟠 Proxied |

## 3. Open 80 and 443 on the monitor VM

GCP → VPC network → Firewall → rule `kuma` → Edit → TCP ports `80,443,3001,3002` → Save.
(3001/3002 get closed again in step 5.)

## 4. HTTPS on the monitor VM

**a. Origin certificate (once, free, valid 15 years):** Cloudflare → `ctfc.live` → **SSL/TLS** → **Origin Server** →
**Create Certificate** → keep the defaults (RSA, `*.ctfc.live` + `ctfc.live`, 15 years) → **Create**.
It shows two boxes. On the monitor VM:
```bash
sudo mkdir -p /etc/caddy
sudo nano /etc/caddy/origin.pem     # paste the "Origin Certificate" box, save
sudo nano /etc/caddy/origin.key     # paste the "Private Key" box, save (shown only once)
```
**b. Install Caddy + config:**
```bash
cd /opt/ctf/ctf-infra && sudo git pull
sudo ./scripts/monitor/setup-https.sh ctfc.live
```
**c.** Cloudflare → SSL/TLS → Edge Certificates: the Universal certificate shows **Active** (5-15 min after the
domain goes active). Then **https://kuma.ctfc.live** and **https://live.ctfc.live** work (same logins as before).

The same origin certificate covers `internal.ctfc.live` and `atc.ctfc.live` later (it's `*.ctfc.live`):
copy the two files to the platform's nginx.

Kuma → Settings → General → **Primary Base URL** = `https://kuma.ctfc.live` (links in notifications).

## 5. Close the raw ports

Everything now goes through HTTPS, so the old `http://IP:3001` / `:3002` should stop being reachable from the internet.

1. GCP firewall rule `kuma` → TCP ports `80,443` only → Save.
2. New rule `live-internal`: target tag `kuma`, source `10.128.0.0/9` (GCP internal), TCP `3002`
   → GCP servers' agents keep using `http://<monitor internal IP>:3002`.
3. Agents on **Contabo** (not in GCP's network) use `LIVE_URL=https://live.ctfc.live` instead
   (Servers tab → Board address → `https://live.ctfc.live`).

## 6. Later: the CTF itself

When the Contabo servers exist (docs/07): add `internal` (🟠) and `chal1` (⚪), set each challenge server's
**Public address** in CTFd Docker Config to `chal1.ctfc.live`. Moving servers is then only a DNS change.

## Optional: login wall for Kuma and the board

Cloudflare → Zero Trust (free up to 50 users) → Access → Applications → Add → Self-hosted →
`kuma.ctfc.live` and `live.ctfc.live` → policy: emails of the organizers. Anyone else can't even reach the login page.
Don't do this for `internal.ctfc.live` (players) or `chal1` (not proxied).
