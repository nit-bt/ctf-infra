# 05 · Challenges

## Internal CTF set (17)

| Category | Count | Type |
|---|---|---|
| Forensics | 4 | static (file download) |
| OSINT | 5 | static |
| Crypto | 4 | 2 static, **2 instanced** |
| Web | 4 | **all instanced** |

Static = normal CTFd challenge with a file/flag. Instanced = `docker` type, each player gets their own container.

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
| Auto-removed | after 2 h, or when the challenge is solved |
| Admin | Docker Status page: see / kill any container, nuke all |
