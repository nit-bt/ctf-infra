# 05 · Challenges

## Internal CTF set (17)

| Category | Count | Type |
|---|---|---|
| Forensics | 4 | static (file download) |
| OSINT | 5 | static |
| Crypto | 4 | 2 static, **2 instanced** |
| Web | 4 | **all instanced** |

Static = normal CTFd challenge with a file/flag. Instanced = `docker` type, each player gets their own container.

## Static challenges

Static = the player downloads a file (or just reads the description) and solves it on their own machine.
The **file is the puzzle** (pcap, image, disk image, `encrypt.py` + `output.txt`…), the flag is hidden inside it.
The correct flag is told to CTFd separately.

CTFd stores uploaded files itself (platform: `.data/CTFd/uploads`), no challenge server involved.

### Option A: click it in
Admin → Challenges → **+** → type **standard** → name, category, description, value → **Create** → flag → **Finish** → **Files** tab → upload → **Visible**.

### Option B: ctfcli (recommended for many challenges, and for moving to Contabo)

Keep every challenge as a folder in a private git repo, cloned on the platform at `/opt/ctf/challenges`:
```
/opt/ctf/challenges/
├── .ctf/config              ← CTFd URL + admin token, NEVER commit
├── .gitignore               ← .ctf/config
├── forensics/lost-packets/
│   ├── challenge.yml        ← name, points, flag, files, hints
│   ├── dist/capture.zip     ← what players download
│   └── solve/writeup.md     ← solution, not uploaded
└── osint/where-am-i/
    └── challenge.yml
```

`challenge.yml`:
```yaml
name: "Lost Packets"
author: "okie"
category: Forensics
description: |
  We captured some traffic from a suspicious laptop.
value: 100
type: standard
flags:
  - flag{h1dd3n_1n_th3_p4ck3ts}          # exact match
  - type: static
    content: flag{hidden_in_the_packets}
    data: case_insensitive               # any case
files:
  - dist/capture.zip
hints:
  - content: "Follow the TCP stream"
    cost: 10
state: hidden
version: "0.1"
```

One-time setup:
```bash
sudo apt install -y pipx && pipx install ctfcli && pipx ensurepath    # log out/in
cd /opt/ctf/challenges && echo ".ctf/config" >> .gitignore
ctf init --no_commit
#   URL:   http://localhost
#   token: CTFd → Settings → Access Tokens → Generate (as admin)
#   integrations: Enter · confirm: y
```

Daily use:
```bash
ctf challenge add forensics/lost-packets    # register a new folder (once)
ctf challenge install                       # create new ones in CTFd
ctf challenge sync --ignore solution        # push edits (flag, points, files, state)
```

Gotchas (found while testing on CTFd 3.7.7 + ctfcli 0.1.8):
- `ctf init` **commits the admin token** into git unless you pass `--no_commit`.
- `sync` without `--ignore solution` crashes on 3.7.7 (it calls a CTFd 3.8 endpoint) and stops **before** applying `state`.
- `install` skips challenges that already exist; use `sync` for those.

## Build an instanced challenge image

Rules:
- **Expose** the port the service listens on (`EXPOSE 80` / `EXPOSE 1337`). The plugin publishes every exposed port.
- **No network at runtime.** Install everything at build time.
- Runs as a normal user if possible; `no-new-privileges` is on, so **setuid privesc challenges won't work** (tell the plugin maintainer first if you need one).
- 256 MB / 0.5 CPU by default. Keep it small.
- Name: `ctf/<category>-<name>:latest`, e.g. `ctf/web-login:latest`.

Web example:
```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir flask
WORKDIR /app
COPY app.py flag.txt ./
RUN useradd -m ctf && chown -R root:root /app && chmod 444 /app/flag.txt
USER ctf
EXPOSE 5000
CMD ["python", "app.py"]
```

Crypto (`nc`) example:
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends socat && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY chall.py flag.txt ./
RUN useradd -m ctf
USER ctf
EXPOSE 1337
CMD ["socat", "TCP-LISTEN:1337,reuseaddr,fork", "EXEC:python3 /app/chall.py,stderr"]
```

## Get it onto the challenge server

Simplest (build on the server):
```bash
cd /opt/ctf/challenges/web-login
sudo docker build -t ctf/web-login:latest .
```

With several servers: build once, push to a **private** registry (Docker Hub private repo / GHCR), `docker pull` on each server. Never put flags in a public image.

Quick test on the server before CTFd:
```bash
sudo docker run --rm -p 30500:5000 ctf/web-login:latest
curl http://127.0.0.1:30500
```

## Add it in CTFd

1. Docker Config → the server → tick the new repo in **Allowed repositories** → Save
2. Challenges → **+** → type **docker**
3. **Docker Host** → the server, **Docker Image** → `ctf/web-login:latest`
4. Connection info:
   - web: `http://host:port`
   - netcat: `nc host port`

   `host` and `port` are filled in per player when they start their instance.
5. Flag, value, then **Visible** when ready. Admins can start instances of hidden challenges to test.

## Player rules (from the plugin)

| | |
|---|---|
| Containers at once | 1 per player (Teams mode: 1 per team) |
| Stop | any time; then 30 s before restarting that challenge |
| Revert (fresh container) | after 5 min |
| Auto-removed | when the challenge is solved, or after 2 h (checked at most once a minute while people use the site, and whenever an admin opens Docker Status) |
| Admin | Docker Status page: see / kill any container, nuke all |
