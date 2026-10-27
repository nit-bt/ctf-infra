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

## Platform: changes to CTFd's compose file

**1. Remove the public port 8000.** Docker-published ports skip `ufw`, so this would expose CTFd directly. In `docker-compose.yml`, under `ctfd:` delete:
```yaml
    ports:
      - "8000:8000"
```

**2. Fixed secret key** (otherwise everyone is logged out on every restart):
```bash
cd /opt/ctf/CTFd
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
chmod 600 .env
```
and under `ctfd: environment:` add `- SECRET_KEY=${SECRET_KEY}`. Back up `.env` with the DB.

**3. Change DB passwords** from `ctfd` (`MARIADB_PASSWORD`, `MARIADB_ROOT_PASSWORD`, and the password in `DATABASE_URL`). DB is on an internal-only network, but don't ship defaults.

**4. More workers for ATC** *(to test)*: `WORKERS=1` is fine for 25 players; try 2-4 for 100 and load-test.

## Domain + HTTPS *(to test)*

Domain via GitHub Student Pack: **`.me` or `.tech`**. Not `.dev` / `.app`: browsers force HTTPS on those, which breaks `http://host:port` instances.

| Record | Points to | Cloudflare |
|---|---|---|
| `ctf.<domain>` | platform IP | 🟠 proxied (hides IP, DDoS protection) |
| `chal1.<domain>` … | challenge server IP | ⚪ DNS only (Cloudflare can't pass ports 30000-31000) |

- Cloudflare SSL mode **Full (strict)** + **Origin certificate** on the platform's nginx (port 443)
- Lock platform 80/443 to Cloudflare IP ranges (needs `DOCKER-USER` rules like the challenge firewall, since Docker skips `ufw`)
- In Docker Config, set each server's **Public address** to `chalN.<domain>`, then moving servers = only a DNS change

## Backups

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
