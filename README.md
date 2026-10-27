# ctf-infra

Runbook + scripts for our CTF platform: **CTFd + instanced Docker challenges**, spread over several challenge servers.

Built first in a **GCP sandbox**, then replayed on **Contabo** for the real events.

| Event | When | Format | Servers |
|---|---|---|---|
| Internal CTF | Nov 2026, 3rd week, 9:00-17:00, online | ~25 players, **solo** (Users mode), 17 challenges | 1 platform + 1 challenge server |
| ATC CTF | 21 Feb 2027, on-site at AUPP | ~100 players, teams of 4 (Teams mode) | 1 platform + 3 challenge servers |

## How it fits together

```
 players (browser / nc)
   │                         │
   │ 80/443                  │ 30000-31000 (their own instance)
   ▼                         ▼
┌──────────────────┐   ┌───────────────────────────────┐
│ platform         │   │ challenge server(s)           │
│ nginx → CTFd     │──►│ Docker API :2376 (TLS + cert) │
│ MariaDB, Redis   │   │ one container per player      │
│ plugin: docker   │   │ firewall: containers can't    │
│   challenges     │   │   start any connection        │
└──────────────────┘   └───────────────────────────────┘
        private network / platform IP only ▲
```

- CTFd talks to each challenge server's Docker API over **TLS with a client certificate**.
- Each docker challenge is pinned to one challenge server (e.g. web → server 1).
- Players get `http://host:port` / `nc host port` for **their own** container.

Plugin (our fork, multi-host): **https://github.com/nit-bt/CTFd-Docker-Challenges**
It also holds `setup-docker-tls.sh` and the `firewall/` scripts.

## Order of work

| # | Doc | What |
|---|---|---|
| 1 | [docs/01-gcp-sandbox.md](docs/01-gcp-sandbox.md) | GCP project, org policies, VMs, firewall rules |
| 2 | [docs/02-server-base.md](docs/02-server-base.md) | Team users, SSH, Docker (every server) |
| 3 | [docs/03-platform.md](docs/03-platform.md) | CTFd 3.7.7 + plugin |
| 4 | [docs/04-challenge-server.md](docs/04-challenge-server.md) | Docker API TLS, connect to CTFd, firewall |
| 5 | [docs/05-challenges.md](docs/05-challenges.md) | Building and adding instanced challenges |
| 6 | [docs/06-testing.md](docs/06-testing.md) | End-to-end checklist |
| 7 | [docs/07-production-contabo.md](docs/07-production-contabo.md) | Moving to Contabo, domain, HTTPS, backups |
| - | [branding/](branding/) | Club look: logo, favicon, theme, home page |
| - | [docs/emergency.md](docs/emergency.md) | **Event day:** alert → fix, fire drill |
| - | [docs/failover.md](docs/failover.md) | GCP spares: backups every 15 min, switch over if a Contabo server dies |
| - | [docs/troubleshooting.md](docs/troubleshooting.md) | Every error we hit and the fix |
| - | [docs/decisions.md](docs/decisions.md) | Why things are the way they are |
| - | [docs/reports/](docs/reports/) | Test reports (load test 27 Oct: PASS) |

## Scripts

| Script | Run on | Does |
|---|---|---|
| `scripts/install-docker.sh` | every server | Docker CE from Docker's official repo |
| `scripts/setup-users.sh` | every server | team users, SSH keys, sudo, `/opt/ctf`, SSH hardening |
| `scripts/backup-ctfd.sh` | platform | DB dump + uploads → `.tar.gz`, pushed to the GCP spare |
| `scripts/restore-ctfd.sh` | platform / spare | load a backup into CTFd |
| `scripts/setup-backup-receiver.sh` | GCP spare platform | user that can only receive backups |
| `scripts/alerts/` | every server | phone alerts (Telegram/Discord) when something breaks, see [emergency](docs/emergency.md) |
| plugin repo: `setup-docker-tls.sh` | challenge servers | Docker API on :2376 with TLS + client certs |
| plugin repo: `firewall/harden-chal-host.sh` | challenge servers | block container egress, lock :2376 to the platform |

## Rules

- **Never commit** certs, keys, `.env`, backups (see `.gitignore`).
- Test on GCP first, then Contabo.
- If you fix something by hand on a server, put it in a script or a doc here.
