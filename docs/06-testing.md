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
