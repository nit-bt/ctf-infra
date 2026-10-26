#!/usr/bin/env bash
# Install Docker CE from Docker's official apt repo (Ubuntu). Safe to re-run.
#   sudo ./scripts/install-docker.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo $0"
  exit 1
fi

echo "[1/5] Removing old/conflicting packages..."
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  apt-get remove -y "$pkg" >/dev/null 2>&1 || true
done

echo "[2/5] Installing prerequisites..."
apt-get update -y
apt-get install -y ca-certificates curl

echo "[3/5] Adding Docker GPG key..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "[4/5] Adding Docker repo..."
CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

echo "[5/5] Installing Docker..."
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo
echo "=== Done ==="
docker --version
docker compose version
docker run --rm hello-world | grep "Hello from Docker"
