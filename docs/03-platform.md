# 03 · Platform (CTFd + plugin)

## Why CTFd 3.7.7 exactly

The docker plugin is built and tested for **3.7.7**. Don't use the latest tag (3.8.x) without testing the plugin on it first.

## Install

```bash
cd /opt/ctf
git clone https://github.com/CTFd/CTFd.git
cd CTFd && git checkout 3.7.7

cp -r /opt/ctf/CTFd-Docker-Challenges/docker_challenges CTFd/plugins/
sudo docker compose up -d
sudo docker compose ps          # ctfd, db, cache, nginx = Up (not Restarting)
```

First start takes ~1 min (DB migrations). Open `http://<platform-ip>` → setup wizard:
- **User Mode** for the internal CTF (solo), **Team Mode** for ATC
- strong admin password, saved in the team password manager

Check: **Admin → Plugins** shows **Docker Config** and **Docker Status**.

## Update the plugin

```bash
cd /opt/ctf/CTFd-Docker-Challenges && git pull
cp -r docker_challenges ../CTFd/CTFd/plugins/
cd ../CTFd && sudo docker compose restart ctfd
```
Then `Ctrl+Shift+R` in the browser (the challenge page JS changes too).

CTFd's container mounts the source folder (`.:/opt/CTFd:ro`), so a **restart** is enough, no rebuild.

## Starting over

```bash
sudo docker compose down
sudo rm -rf .data        # DB, uploads, logs. `down -v` does NOT remove these
sudo docker compose up -d
```

## Things to know

- **Port 8000** (CTFd directly, skipping nginx) is published by the default compose file. GCP firewall blocks it; on Contabo **remove it**, see [07](07-production-contabo.md).
- **Secret key**: CTFd can't write `.ctfd_secret_key` because its folder is mounted read-only, so it makes a new key on every restart → everyone gets logged out. Fine in sandbox; set `SECRET_KEY` for production ([07](07-production-contabo.md)).
- **Admin = root on challenge servers.** The Docker client key is stored in CTFd's DB. Few admins, strong passwords, never expose MariaDB.
