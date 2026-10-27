# Monitoring dashboard (Uptime Kuma), for every event

One permanent server, separate from all event servers, that watches them from outside:
dashboard, history, Telegram alerts, optional public status page for players.

Works next to `ctf-alert` (docs/emergency.md), it doesn't replace it:

| | ctf-alert (on each event server) | Uptime Kuma (this server) |
|---|---|---|
| RAM, disk, firewall, killed containers, CTFd containers | ✅ | ❌ |
| Whole server / site down, seen from outside | via PEERS | ✅ |
| Dashboard, history, status page | ❌ | ✅ |

## 1. The VM (GCP free tier, once)

Compute Engine → **Create instance**:

| Field | Value | Why |
|---|---|---|
| Name | `ctf-monitor` | |
| Region | **us-central1** (or us-west1 / us-east1) | free tier is US-only; it doesn't matter where you are |
| Machine | **e2-micro** | the free one |
| Boot disk | Ubuntu 24.04 LTS, **Standard persistent disk**, 30 GB | the default (Balanced) is **not** free, ~$3/month |
| Firewall | tick nothing; add the rule below | |

VPC network → Firewall → **Create rule**: name `kuma`, targets *Specified target tags* `kuma`, source `0.0.0.0/0`, TCP `3001`. Then edit the VM → Network tags → `kuma`.

Cost: VM + disk free; the **external IPv4 is ~$3.65/month** (Google charges for IPv4 on every VM). Paid from credit while it lasts.
When the free trial ends, GCP asks to upgrade to a paid account: do it, or the VM is stopped.
VPC network → IP addresses → **reserve** its external IP (static), so it doesn't change.

## 2. Install (SSH into it)

```bash
# 1 GB RAM is tight: add 1 GB swap
sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

sudo apt update && sudo apt install -y docker.io
sudo docker run -d --name uptime-kuma --restart=always \
  -p 3001:3001 -v uptime-kuma:/app/data louislam/uptime-kuma:1
```

Open `http://<monitor-ip>:3001` → create the admin account (strong password) → **Settings → Security → enable 2FA**.
It's on the internet; the login + 2FA is what protects it. Later, with a domain, put it behind HTTPS (e.g. `status.<domain>` via Cloudflare).

## 3. Telegram (once)

Settings → **Notifications** → Setup Notification → **Telegram**
- Bot token + chat ID: the same bot as ctf-alert (docs/emergency.md)
- tick **Default enabled** and **Apply on all existing monitors** → Test → Save

## 4. Per event: add its servers (2 min)

Add New Monitor, one per line, interval 60 s, retries 2 (so one slow check isn't an alert):

| Monitor type | Target | Shows |
|---|---|---|
| HTTP(s) - Keyword | `https://ctf.<domain>/`, keyword `CTFd` | site up and really serving CTFd |
| Ping | platform IP | server alive |
| Ping | each challenge server IP | server alive |
| TCP Port | a challenge server IP, port `22` | server alive even if ping is blocked |

Don't monitor port 2376: the challenge firewall only lets the platform in (correct), so Kuma would see it as down.
Group them per event (e.g. tag `internal-2026-11`) and **pause** them when the event's servers are gone.

## 4b. Connect each server's ctf-alert (Push monitors)

Kuma then shows the inside checks too (RAM, disk, firewall, CTFd containers) and the RAM % as a graph,
and alerts if a server stops reporting (= dead), with no PEERS needed.

Per server:
1. Kuma → Add New Monitor → type **Push** → name = server name (e.g. `internal-chal-1`) → Heartbeat interval **60**, Retries **2**.
2. Copy the **Push URL** it shows → Save.
3. On that server: `sudo nano /etc/default/ctf-alert` → `KUMA_PUSH_URL="<the push URL>"` → save.
4. `sudo ctf-alert test` → the monitor turns green in Kuma.

Avoid double messages: ctf-alert already sends the detailed Telegram alerts, so on **Push monitors**
untick the Telegram notification (they're for the dashboard). Keep Telegram on the **HTTP / Ping**
monitors: those catch a dead server or site from outside. Result: every problem pings you once.

| Problem | Who tells you |
|---|---|
| RAM / disk / firewall / container down / instances killed | ctf-alert (Telegram), also red in Kuma |
| Server dead or unreachable | Kuma Ping monitor (Telegram) |
| Site down from outside (DNS, HTTPS, Cloudflare) | Kuma HTTP monitor (Telegram) |

## 5. Status page for players (optional)

Status Pages → New → name it after the event → add the site + server monitors → Save → share the link in the players' channel.
Players check it before messaging "site down??".

## Updating

```bash
sudo docker pull louislam/uptime-kuma:1 && sudo docker rm -f uptime-kuma
sudo docker run -d --name uptime-kuma --restart=always -p 3001:3001 -v uptime-kuma:/app/data louislam/uptime-kuma:1
```
Data stays in the `uptime-kuma` volume.
