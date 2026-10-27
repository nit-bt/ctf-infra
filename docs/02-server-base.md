# 02 · Base setup (every server)

## 1. Update + get this repo

```bash
sudo apt update && sudo apt upgrade -y
sudo mkdir -p /opt/ctf && sudo chown $USER:$USER /opt/ctf
cd /opt/ctf
git clone https://github.com/nit-bt/ctf-infra.git          # private: needs a token or deploy key
git clone https://github.com/nit-bt/CTFd-Docker-Challenges.git
```

Private repo on a server: use a **read-only deploy key** per server.
```bash
ssh-keygen -t ed25519 -C "$(hostname)" -f ~/.ssh/ctf-infra -N ""
cat ~/.ssh/ctf-infra.pub     # GitHub → ctf-infra → Settings → Deploy keys → Add (no write access)
cat >> ~/.ssh/config <<'EOF'
Host github-ctf
  HostName github.com
  User git
  IdentityFile ~/.ssh/ctf-infra
EOF
git clone git@github-ctf:nit-bt/ctf-infra.git
```

## 2. Docker

```bash
sudo /opt/ctf/ctf-infra/scripts/install-docker.sh
```
Ends with `Hello from Docker!`. Uses Docker's own apt repo (the `get.docker.com` script is meant for testing).

Use `sudo docker …`. Don't add people to the `docker` group: it's root without a password and without a log.

## 3. Team users (Contabo / any non-GCP box)

Each person, on **their** laptop:
```bash
ssh-keygen -t ed25519 -C "name-ctf"
cat ~/.ssh/id_ed25519.pub        # send this line to the admin
```

Admin, on the server:
```bash
sudo /opt/ctf/ctf-infra/scripts/setup-users.sh add okie "ssh-ed25519 AAAA... okie-ctf"
sudo /opt/ctf/ctf-infra/scripts/setup-users.sh list
```
Each user: own login, `sudo` with **their own password** (every sudo command is logged with their name), member of `ctfteam` → can work in `/opt/ctf`.

Test from their laptop: `ssh okie@<server-ip>` → `sudo whoami` → `root`.

When everyone can log in:
```bash
sudo /opt/ctf/ctf-infra/scripts/setup-users.sh harden-ssh
```
→ keys only, no root login. **Keep your current session open** and test a new login in a second terminal before closing it.

Who did what: `sudo journalctl _COMM=sudo` · Remove someone: `setup-users.sh remove <user>`

> GCP sandbox: Google manages users via the browser SSH button instead, see [01](01-gcp-sandbox.md#sudo-stops-working-after-a-few-minutes).
