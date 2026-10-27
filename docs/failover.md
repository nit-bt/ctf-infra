# Failover to the GCP spares

Live servers are on Contabo. GCP keeps one spare of each, always on:

| Contabo (live) | GCP spare | Spare's job |
|---|---|---|
| Platform (CTFd) | `ctf-platform` | receives a backup every 15 min; becomes the site if Contabo's platform dies |
| Challenge server | `ctf-chal-1` | images built, TLS set up; takes over instanced challenges if Contabo's challenge server dies |

What a failover costs: up to **15 min of solves** (since the last backup) and players re-open their instances.
Everything else (accounts, scores, challenges, files) comes back.

---

## A. Before the event (once, then the drill)

Addresses first: a failover is only quick if nothing has to be looked up or re-typed on the day.

1. **Static IPs on GCP.** VPC network > IP addresses > reserve the external IP of both spare VMs.
   An ephemeral IP changes on every stop/start and breaks everything below.
2. **Cloudflare DNS** (docs/07):
   - `ctf.<domain>` → Contabo platform, **proxied** 🟠: switching it to GCP takes effect in seconds, no TTL wait.
   - `chal1.<domain>` → Contabo challenge server, DNS only, **TTL 1 min**.
   - Put the **same Cloudflare origin certificate** on both platforms' nginx, so HTTPS works on GCP the moment DNS points there.
3. **Spare platform ready:** CTFd installed exactly like Contabo (docs/03: same CTFd version, same plugin, `docker-compose.yml`). Theme doesn't matter, the restore brings it.
4. **Backups flow to the spare:**
   ```bash
   # on the CONTABO platform
   sudo ssh-keygen -t ed25519 -N "" -f /root/.ssh/ctfd-backup -C ctfd-backup
   sudo cat /root/.ssh/ctfd-backup.pub                 # copy this line

   # on the GCP spare platform
   cd /opt/ctf/ctf-infra && sudo ./scripts/setup-backup-receiver.sh "ssh-ed25519 AAAA... ctfd-backup"
   # GCP firewall rule: allow tcp:22 from the Contabo platform IP only

   # back on CONTABO
   echo 'OFFSITE="ctfbackup@<gcp-spare-platform-ip>:"' | sudo tee /etc/default/ctfd-backup
   sudo /opt/ctf/ctf-infra/scripts/backup-ctfd.sh       # must end with "Pushed."
   ```
   Then cron (`sudo crontab -e`), every 15 min on event day:
   ```
   */15 8-18 * * * /opt/ctf/ctf-infra/scripts/backup-ctfd.sh >> /var/log/ctfd-backup.log 2>&1
   ```
5. **Spare challenge server ready:**
   - Same setup as Contabo's (docs/04): Docker + `setup-docker-tls.sh` + every instanced challenge image built (`sudo docker images` shows the same names).
   - Firewall allows **both** platforms on 2376: `sudo ./firewall/harden-chal-host.sh <contabo-platform-ip>,<gcp-platform-ip>`
   - Do the same on the **Contabo** challenge server (so a GCP platform can use it too).
   - In CTFd (Contabo) > Admin > Docker Config, **add it as a host** named `spare`, Public address = its IP. It should show **UP**. No challenge uses it yet.
6. **Drill** (about 30 min, on a quiet day). Do scenarios B and C below for real, then switch back. Time yourself.

---

## B. Contabo CHALLENGE server dead (platform fine)

Static challenges keep working. Instanced ones fail to start.

1. Is it really dead? Contabo panel → Reboot, wait 3 min. Back? Admin > Docker Config shows **UP** → done, players press Start.
2. Still dead → Admin > Challenges → each **instanced** challenge → Host: **spare** → Update. (6 challenges, about 2 min.)
3. Post in the players' channel: *"Instances moved to a backup server. Close and reopen the challenge, press Start."*
4. Later, when Contabo is back: switch the challenges back to the original host after the event (or at a quiet moment).

## C. Contabo PLATFORM dead (site down)

1. Is it really dead? Contabo panel → Reboot, wait 3 min. Site back? Done (data is on its disk).
2. Still dead → on the **GCP spare platform**:
   ```bash
   cd /opt/ctf/ctf-infra && git pull
   ls -lt /srv/ctfd-backups | head -3                    # newest backup: how old is it?
   sudo ./scripts/restore-ctfd.sh                       # restores the newest, type RESTORE
   ```
3. Cloudflare → DNS → `ctf.<domain>` → change IP to the **GCP spare platform** → Save. Works within seconds (proxied).
4. Admin > Docker Config: hosts **UP**?
   - Contabo challenge server still alive → it is, because its firewall allows the GCP platform (step A5).
   - Dead too → scenario B step 2 (switch challenges to **spare**).
5. Post in the players' channel: *"Site moved to a backup server. Log in again. Solves after HH:MM may be missing, re-submit those flags."* (HH:MM = backup time.)
6. Stop the cron backup on the dead Contabo box if it comes back, so it doesn't overwrite anything: the spare is now the live site.

## D. Both Contabo servers dead

C, then B. About 20-30 min total if A was done.

---

**After any failover:** take a manual backup on whichever platform is now live, and copy it to your laptop:
`sudo /opt/ctf/ctf-infra/scripts/backup-ctfd.sh` then `scp`.
