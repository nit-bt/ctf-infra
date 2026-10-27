# 06 · Testing checklist

Do this after every new server, and again the day before the event.

## Platform
- [ ] `sudo docker compose ps`: ctfd, db, cache, nginx all **Up**
- [ ] Site loads, admin login works
- [ ] Admin → Plugins → Docker Config: every host **UP**

## Challenge server
- [ ] `setup-docker-tls.sh` printed `OK` + `rejected, good`
- [ ] `harden-chal-host.sh` self-test `6 passed, 0 failed`
- [ ] `sudo ctf-docker-firewall status` shows rules after a reboot

## As a player (incognito window, test account)
- [ ] Open an instanced challenge → **Start Docker Instance**
- [ ] Shows `Host: <public address> Port: 30xxx` and a red **Stop**
- [ ] Connection link opens the challenge (web) / `nc host port` connects (crypto)
- [ ] **Stop** works immediately; **Start** again right away → "wait ~30 seconds"
- [ ] Start a second, different challenge while one runs → "only run one container"
- [ ] Submit the right flag → container disappears (Docker Status empty)

## Admin
- [ ] Docker Status shows running containers with host + address
- [ ] 🗑️ kills one, **Nuke All** kills all

## Load (before the event)

Automated: 25 fake players press Start at the same moment (plugin repo `tools/load-test.py`).
On the platform server:
```bash
cd /opt/ctf/CTFd-Docker-Challenges && git pull
export CTFD_TOKEN=ctfd_xxx      # CTFd -> Settings -> Access Tokens -> Generate (as admin)
python3 tools/load-test.py
# ctf-chal-ports limited to your IP? add per server:  --map <chal-public-ip>=<chal-private-ip>
```
While it waits at "Press Enter", on each challenge server: `sudo docker stats --no-stream ; free -h`.

- [ ] `Started OK 25 / 25`, `Reachable 25 / 25`, ends with `PASS`
- [ ] Median start time a few seconds at most
- [ ] RAM on each challenge server well under its total
- [ ] Nothing restarting: `sudo docker ps -a --filter status=restarting`
- [ ] Then 4-5 real people for a "feels OK" check

Notes:
- Fake players are `loadtest-01..25`, **hidden** from the scoreboard. `--delete-users` removes them; do that before the event.
- Logins go in batches of 9 with 5.5 s pauses (CTFd allows 10 logins per IP and resets its 5 s timer on every login), so setup takes ~20 s.
- Users mode only, for now.
- Tested locally (CTFd 3.7.7, SQLite, fake Docker hosts): 25/25 in 0.9 s; with one host down, the other host's players still start fine. Real numbers on MariaDB + real containers: run it.

## Expected behaviour that looks like a bug
- Instance "already running" after a CTFd restart → containers live on the challenge server, CTFd just remembers them. Stop it or wait for the 2 h cleanup.
- Inside the container `ping google.com` fails → correct, containers have no network out.
- nginx test page says `Server address: 172.17.0.x` → that's the container's Docker-internal IP, normal.

## Crash test (sandbox only)

Goal: find where one challenge server breaks, and check the alerts catch it. Each stress instance holds
~230 MB and burns its CPU share. On an 8 GB server about 30 fit; more than that should break it.

**Setup (once)**
1. Challenge server: `sudo git clone https://github.com/nit-bt/CTFd-Docker-Challenges.git /opt/ctf/CTFd-Docker-Challenges` (or `sudo git -C /opt/ctf/CTFd-Docker-Challenges pull`), then `cd /opt/ctf/CTFd-Docker-Challenges/tools/stress-image && sudo docker build -t ctf/stress .`
2. CTFd → Admin → Docker Config → that host → tick `ctf/stress:latest` in the repositories → Update.
3. Admin → Challenges → Create → type **docker**, name `STRESS`, image `ctf/stress:latest`, any flag, State **Hidden**. Note its ID.
4. Open `#ctf-status`, `#ctf-alerts`, Kuma, and an SSH window on the challenge server running `watch -n2 free -h`.

**Run in steps** (on the platform, `export CTFD_TOKEN=...` first; `--keep` leaves them running):
```bash
cd /opt/ctf/CTFd-Docker-Challenges/tools
python3 load-test.py --chal <ID> --players 20 --keep    # ~4.6 GB: fine
python3 load-test.py --chal <ID> --players 30 --keep    # ~7 GB: RAM alert (85 %) expected
python3 load-test.py --chal <ID> --players 45 --keep    # ~10 GB on 8 GB: should break
```

**Write down at each step:** RAM (`free -h`), load (`uptime`), how long starts take, what the alerts said and
how fast, whether the platform and other players' instances still work, and what the kernel killed
(`sudo journalctl -k | grep -i "out of memory"`).

**Recover**
- Admin → Docker Status → **Nuke All**, or on the server `sudo docker rm -f $(sudo docker ps -q)`
- Server not answering at all: GCP console → VM → **Reset**
- Afterwards: delete the STRESS challenge, and Admin → Users → search `loadtest` → select all → delete
