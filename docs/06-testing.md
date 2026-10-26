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
- [ ] 4-5 friends start instances at the same time
- [ ] On the challenge server: `sudo docker stats` (RAM/CPU per container) and `free -h`
- [ ] Nothing restarting: `sudo docker ps -a --filter status=restarting`

## Expected behaviour that looks like a bug
- Instance "already running" after a CTFd restart → containers live on the challenge server, CTFd just remembers them. Stop it or wait for the 2 h cleanup.
- Inside the container `ping google.com` fails → correct, containers have no network out.
- nginx test page says `Server address: 172.17.0.x` → that's the container's Docker-internal IP, normal.
