#!/usr/bin/env bash
# Install CTFd + our docker plugin on a production platform server (Contabo). Safe to re-run.
#   sudo ./scripts/setup-platform.sh
# Does: CTFd $CTFD_VERSION in /opt/ctf/CTFd, plugin copied in, production override (no :8000, fixed
# SECRET_KEY, random DB passwords in .env), build + start, health check. HTTPS comes after (docs/07).
set -euo pipefail

CTFD_VERSION=${CTFD_VERSION:-3.8.9}
BASE=/opt/ctf
HERE=$(cd "$(dirname "$0")/.." && pwd)
PLUGIN=$BASE/CTFd-Docker-Challenges/docker_challenges

if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi
command -v docker >/dev/null || { echo "Docker missing: run scripts/install-docker.sh first"; exit 1; }
[[ -d $PLUGIN ]] || { echo "Plugin missing: git clone https://github.com/nit-bt/CTFd-Docker-Challenges.git in $BASE"; exit 1; }

echo "[1/5] CTFd $CTFD_VERSION"
if [[ ! -d $BASE/CTFd/.git ]]; then
  git clone -q https://github.com/CTFd/CTFd.git "$BASE/CTFd"
fi
cd "$BASE/CTFd"
git fetch -q --tags
git -c advice.detachedHead=false checkout -q "$CTFD_VERSION"
echo "      $(git describe --tags)"

echo "[2/5] Plugin"
rm -rf CTFd/plugins/docker_challenges
cp -r "$PLUGIN" CTFd/plugins/

echo "[3/5] Production settings (.env + override)"
cp "$HERE/platform/docker-compose.override.yml" docker-compose.override.yml
if [[ ! -f .env ]]; then
  umask 077
  cat > .env <<ENV
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 24)
DB_ROOT_PASSWORD=$(openssl rand -hex 24)
WORKERS=2
ENV
  echo "      new .env with random secrets (backed up by backup-ctfd.sh; never commit it)"
else
  for k in SECRET_KEY DB_PASSWORD DB_ROOT_PASSWORD; do
    grep -q "^$k=" .env || { echo "!! .env has no $k. Add it or move .env away to generate a new one"; exit 1; }
  done
  echo "      keeping existing .env"
fi
chmod 600 .env
docker compose config -q

echo "[4/5] Build + start (first build takes a few minutes)"
docker compose up -d --build
docker compose ps --format '      {{.Service}}: {{.State}}'

echo "[5/5] Health check"
up() { docker compose exec -T ctfd python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=5)" >/dev/null 2>&1; }
for i in $(seq 60); do up && break; sleep 3; done
if ! up; then echo "!! CTFd not answering: sudo docker compose -f $BASE/CTFd/docker-compose.yml logs --tail 50 ctfd"; exit 1; fi
if docker compose port ctfd 8000 >/dev/null 2>&1; then echo "!! port 8000 is published, override not applied"; exit 1; fi
echo "CTFd is up behind nginx on port 80 (8000 not public)."
echo "Next: HTTPS + internal.ctfc.live (docs/07), then open the site for the setup wizard."
