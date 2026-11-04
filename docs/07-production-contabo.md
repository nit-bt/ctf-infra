# 07 · Production on Contabo

Status: **plan**. Everything here worked on GCP except the parts marked *(to test)*.

## Servers

| Event | Platform | Challenge servers |
|---|---|---|
| Internal (Nov) | 1 × 4 vCPU / 8 GB | 1 × 4 vCPU / 8 GB |
| ATC (Feb) | same platform, fresh install | 3 × 4 vCPU / 8 GB (web / pwn / reverse) |

Region: Japan (our pick; compare latency with Singapore before ordering).
OS: Ubuntu 26.04 LTS, same as the GCP servers. If Contabo doesn't offer it, 24.04 works with the same scripts.
After the internal CTF: back up, cancel; for ATC set up **fresh** from these docs (different players, Teams mode, new challenges).

## Differences from GCP

| | GCP sandbox | Contabo |
|---|---|---|
| Users / sudo | OS Login | `scripts/setup-users.sh` |
| Network firewall | VPC rules (tags) | **none by default**, the host does it |
| Platform ↔ challenge | private VPC IPs | public IPs (or Contabo private network add-on) |
| Metadata token risk | yes → no service account | no GCP-style tokens, firewall still blocks 169.254.169.254 |

So on Contabo:
- `setup-docker-tls.sh <private-ip> <public-ip>`, cert must include the public IP if CTFd connects over it
- `harden-chal-host.sh <platform-public-ip>`, Docker API then only answers the platform
- Docker API address in CTFd = challenge server's public IP `:2376`

## Platform: install

```bash
sudo /opt/ctf/ctf-infra/scripts/setup-platform.sh
```
CTFd 3.8.9 + plugin, plus the production changes **without editing CTFd's own compose file**
(`platform/docker-compose.override.yml`, values in `/opt/ctf/CTFd/.env`, chmod 600, random on first run):

1. **No public port 8000.** Docker-published ports skip `ufw`; only nginx (80, later 443) is public.
2. **Fixed `SECRET_KEY`** (otherwise everyone is logged out on every restart).
3. **Random DB passwords** instead of `ctfd`.
4. `WORKERS=2`.

`.env` is in every backup (`backup-ctfd.sh`), and `restore-ctfd.sh` puts it back. Never commit it.

**4. More workers for ATC** *(to test)*: `WORKERS=1` is fine for 25 players; try 2-4 for 100 and load-test.

## HTTPS + `internal.ctfc.live`

Cloudflare proxied (🟠) + SSL mode **Full (strict)** + the Cloudflare **origin certificate** (`*.ctfc.live`, the same one
the monitor VM uses in `/etc/caddy/`) on CTFd's nginx.

1. Certificate onto the platform (copy the two files from the monitor VM, e.g. `sudo cat` there, paste here):
   ```bash
   sudo mkdir -p /opt/ctf/certs
   sudo nano /opt/ctf/certs/origin.pem      # paste -----BEGIN CERTIFICATE----- ... END
   sudo nano /opt/ctf/certs/origin.key      # paste -----BEGIN PRIVATE KEY----- ... END
   ```
2. `sudo /opt/ctf/ctf-infra/scripts/setup-platform.sh` again: sees the certificate, switches to
   `platform/docker-compose.override.https.yml` + `platform/nginx-https.conf`:
   443 with the origin certificate, 80 → 301 to HTTPS, **real player IPs from `CF-Connecting-IP`**
   (otherwise CTFd sees Cloudflare's IPs and every player shares one rate limit).
3. Cloudflare → DNS → **A** `internal` → platform IP, **Proxied** 🟠.
4. `https://internal.ctfc.live` → CTFd.

| Record | Points to | Cloudflare |
|---|---|---|
| `internal.ctfc.live` | platform IP | 🟠 proxied (hides IP, DDoS protection) |
| `chal1.ctfc.live` … | challenge server IP | ⚪ DNS only (Cloudflare can't pass ports 30000-31000) |

- In Docker Config, set each server's **Public address** to `chalN.ctfc.live`, then moving servers = only a DNS change
- Then lock 80/443 to Cloudflare's IPs (`harden-platform.sh`), otherwise the raw IP skips Cloudflare

## Hardening (both servers, after `setup-users.sh harden-ssh`)

```bash
sudo /opt/ctf/ctf-infra/scripts/harden-base.sh        # ufw (SSH only), fail2ban, security updates, Copy Fail fix
sudo /opt/ctf/ctf-infra/scripts/harden-platform.sh    # platform only: 80/443 answer only Cloudflare
```
- Challenge server: run `harden-chal-host.sh <platform-ip>` (plugin repo) **first**, then `harden-base.sh`: it reads the
  platform IP from that config and allows 2376 from it in ufw.
- `harden-platform.sh` puts its rules in Docker's `DOCKER-USER` chain (Docker skips ufw), re-applied on every Docker start
  (`ctf-platform-firewall.service`). Anything else a container publishes by mistake is dropped too.
- Check from a laptop: `http://<platform-ip>` times out, `https://internal.ctfc.live` works.
- Undo if the site breaks: `sudo ctf-platform-firewall remove`.
- Event day: stop automatic updates/reboots: `sudo systemctl stop unattended-upgrades apt-daily.timer apt-daily-upgrade.timer`.

## Backups

**Now (Nov 2026):** hourly cron on the Contabo platform, each backup pushed to **`ctf-monitor`** (Always Free e2-micro,
`setup-backup-receiver.sh`, keeps 200), because the GCP platform VM is stopped until event week.
Event week: start the GCP spare, point `OFFSITE` at it instead (docs/failover.md), so a restore there needs no copying.

```bash
sudo /opt/ctf/ctf-infra/scripts/backup-ctfd.sh
scp <user>@<platform>:/opt/ctf/backups/ctfd-*.tar.gz .
```
Daily cron (see script header). Before cancelling a server: final backup, copy it off, check it opens.

**On event day** back up every 15 min, pushed to the GCP spare automatically: see [failover.md](failover.md). Without the spare, at least hourly, and copy the latest one off at lunch and at the end:
```bash
sudo crontab -e
# add:
0 9-17 * * * /opt/ctf/ctf-infra/scripts/backup-ctfd.sh >> /var/log/ctfd-backup.log 2>&1
```

### Restore

Easiest: `sudo ./scripts/restore-ctfd.sh [file]` (newest backup if no file given). By hand:

```bash
mkdir -p /tmp/restore && sudo tar xzf ctfd-YYYYMMDD-HHMM.tar.gz -C /tmp/restore
cd /opt/ctf/CTFd
sudo docker compose stop ctfd                       # players see an error for ~1 min
sudo docker compose exec -T db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"' < /tmp/restore/ctfd.sql
sudo mkdir -p .data/CTFd/uploads && sudo cp -a /tmp/restore/uploads/. .data/CTFd/uploads/
sudo cp -a /tmp/restore/.ctfd_secret_key .
sudo docker compose start ctfd
```
The dump replaces the whole `ctfd` database (users, solves, challenges, config). Instances still running on challenge servers are cleaned up by the sweep. Practise this once on GCP before the event.

### Snapshots (snap back)

Contabo panel → **Servers & Hosting → VPS → More → Create Snapshot**; roll back from the same menu (**Snapshots → Rollback**).
Rules: free, **only 1 per server on our plan** (4 vCPU / 8 GB), **deleted after 30 days**, can't be downloaded, not a backup.
Rolling back to an older snapshot **deletes the newer ones**. Everything written after the snapshot is lost.

| Snapshot | When | Both servers |
|---|---|---|
| `clean` | OS + `harden-base.sh` + Docker done, nothing else | broke the setup → roll back, redo from there |
| `frozen` | day before the event, challenges loaded, test run done, test data removed. **Delete `clean` first** (1 slot) | event-day disaster (hacked, broken config) |

Event-day disaster on the **platform**: roll back to `frozen` (players and solves since then are gone), then bring them back
from the newest backup on the GCP spare: copy `/srv/ctfd-backups/<newest>` to the platform (via your laptop), then
`sudo ./scripts/restore-ctfd.sh /tmp/ctfd-YYYYMMDD-HHMM.tar.gz`. Loss = up to 15 min. Faster if the box is just dead: failover.md scenario C.
Disaster on a **challenge server**: roll back to `frozen`, then Admin → Docker Status → **Nuke All** to clear old instance records.

Cancelling a Contabo VPS **wipes the disk**, snapshots included. Check Contabo's cancellation notice period so you're not billed an extra month.

## Timeline (internal CTF)

| Dates | Where | Work |
|---|---|---|
| Oct 26 - Nov 1 | GCP | platform + plugin + TLS + firewall ✅, then challenge images |
| Nov 2 - 8 | GCP | build 6 images, load all 17 challenges |
| Nov 9 - 10 | Contabo | order servers, replay docs 02-04 + this page, import challenges |
| Nov 11 - 13 | Contabo | test run with 4-5 people ([06](06-testing.md)) |
| Nov 14 | GCP | stop/delete sandbox VMs |
| Nov 14 - 15 | Contabo | freeze, backup, rules page, support channel |
| Comp day | Contabo | 1-2 people on call 9:00-17:00 |

Moving challenges GCP → Contabo: CTFd **Admin → Config → Backup → Export**, then Import on the new one. Re-check each docker challenge's host afterwards (host IDs may differ).
