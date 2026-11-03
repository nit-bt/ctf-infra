# Emergency runbook

Your phone buzzed. Find the message below, run the fix. Each fix is safe to run more than once.

## Alerts setup

The alerts (`ctf-alert`), Kuma and the live board are in the **[ctfc-monitor](https://github.com/nit-bt/ctfc-monitor)** repo
(`/opt/ctfc-monitor` on the servers): setup in its `docs/alerts.md`. This page is what to do when one fires.

**Event day:** check more often on every server: `sudo ctf-alert every 20` (Kuma Push monitors: Heartbeat 40).
After: `sudo ctf-alert every 60` (Kuma back to 90). Watch https://live.ctfc.live.

**Before the event:** install an SSH app on your phone (Termius, JuiceSSH) with your key, and save logins for every server. Do the [fire drill](#fire-drill) once.

## 🔴 "CTFd site not answering" / "CTFd container '…' is not running"
Platform server:
```bash
cd /opt/ctf/CTFd
sudo docker compose ps                      # which one is not Up?
sudo docker compose up -d                   # starts whatever is missing
sudo docker compose logs ctfd --tail 50     # why it died
```
Still down? `sudo docker compose restart ctfd`
Players are logged out after a ctfd restart unless `SECRET_KEY` is set ([07](07-production-contabo.md)).
**Never** change CTFd version or wipe `.data` on event day.

## 🔴 "Docker is not running"
```bash
sudo systemctl restart docker
sudo systemctl status docker --no-pager | head -5
```
- Platform: then `cd /opt/ctf/CTFd && sudo docker compose up -d`
- Challenge server: running player containers are gone. Players reopen the challenge and press **Start**. Check the firewall came back: `sudo ctf-docker-firewall status`

## 🔴 "RAM at …%"
Challenge server:
```bash
sudo docker stats --no-stream | sort -k4 -h | tail -5    # biggest containers last
```
- Kill the worst ones in CTFd → **Docker Status** → 🗑️ (players just start again)
- One challenge always at the top? Hide it for now (Admin → Challenges → **Hidden**) and post a notice
- Lower *Memory / container* for that server in Docker Config (new containers only)

Platform: `sudo docker stats --no-stream`, then `cd /opt/ctf/CTFd && sudo docker compose restart ctfd`

## 🔴 "Disk at …%"
```bash
sudo docker system df                       # what's using space
sudo docker image prune -f                  # only untagged leftovers, safe
sudo journalctl --vacuum-size=200M          # trim system logs
sudo du -sh /opt/ctf/backups 2>/dev/null    # old backups? copy off, then delete
```

## 🟡 "container(s) killed for using too much RAM"
Not urgent: that player's instance died. When they reopen the challenge, the Start button is back (plugin `5aea38a`+), so they just press Start.
Same challenge again and again → it needs more than 256 MB: raise the limit or hide it ([05](05-challenges.md)).

## 🔴 "Challenge firewall is OFF"
```bash
sudo systemctl restart ctf-docker-firewall
sudo ctf-docker-firewall status
```
Containers could reach the internet while it was off. Fix this one fast.

## 🔴 "Docker API (2376) not answering"
CTFd can't start instances on that server (shows **DOWN** in Docker Config).
```bash
sudo systemctl restart docker
sudo journalctl -u docker -n 30 --no-pager
```

## 🔴 "Can't reach <server>"
The other server is down or unreachable.
1. Provider panel (GCP console / Contabo panel) → is it running? → **Start** / **Reboot**
2. Reboot didn't help → Contabo panel → **VNC console** (works without network)
3. GCP: an ephemeral IP changes on stop/start → update *Public address* in Docker Config
4. After a challenge server comes back: CTFd → Docker Config → host **UP**?

## 🔴 A whole Contabo server is dead (reboot didn't help)
Switch to the GCP spare: [failover.md](failover.md) scenario **B** (challenge server) or **C** (platform).

## Players say…
| "…" | Do |
|---|---|
| "My instance doesn't load" | Close and reopen the challenge: a dead instance is detected and Start comes back. Otherwise Stop → Start. Many people at once → is that host **UP** in Docker Config? |
| "Could not start container" | Host DOWN → section above. "Image not available" → repo not ticked in Docker Config |
| "Please wait N seconds" / "still running" | Normal, wait and retry |
| "Challenge X is broken" | Hide it, fix calmly, unhide, post a notice |

## Big switches
| Need | Where |
|---|---|
| Hide one challenge | Admin → Challenges → challenge → State **Hidden** |
| Kill every instance | Admin → Plugins → Docker Status → **Nuke All** (players start again) |
| Pause / extend the event | Admin → Config → **Start and End Time** |

Always post in the players' channel what's happening and roughly when it'll be back.

## Fire drill
Do once before the event, with alerts switched on. Each step should buzz your phone, then send ✅ after the fix.
1. Platform: `sudo docker stop ctfd-ctfd-1` → alert → `cd /opt/ctf/CTFd && sudo docker compose up -d`
2. Challenge server: `sudo systemctl stop ctf-docker-firewall` → alert → fix above
3. Stop a whole challenge server in the provider panel → the platform reports it → start it again
