#!/usr/bin/env bash
# Team accounts on a server: own user + SSH key + sudo (with password), shared /opt/ctf.
#
#   sudo ./scripts/setup-users.sh add <username> "<ssh-public-key>"
#   sudo ./scripts/setup-users.sh remove <username>
#   sudo ./scripts/setup-users.sh harden-ssh      # key-only login, no root login
#   sudo ./scripts/setup-users.sh list
#
# Each person makes a key on THEIR laptop:  ssh-keygen -t ed25519 -C "name-ctf"
# and sends you the line from ~/.ssh/id_ed25519.pub
set -euo pipefail

GROUP=ctfteam
WORKDIR=/opt/ctf

if [[ $EUID -ne 0 ]]; then echo "Run with sudo"; exit 1; fi

ensure_workdir() {
  getent group "$GROUP" >/dev/null || groupadd "$GROUP"
  mkdir -p "$WORKDIR"
  chown root:"$GROUP" "$WORKDIR"
  chmod 2775 "$WORKDIR"   # setgid: new files stay group-owned
}

cmd_add() {
  local user=$1 key=$2
  [[ $user =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || { echo "Bad username: $user"; exit 1; }
  [[ $key =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256)\  ]] || { echo "That doesn't look like an SSH public key"; exit 1; }
  ensure_workdir
  if ! id "$user" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" "$user"
    echo "Set a sudo password for $user:"
    passwd "$user"
  fi
  usermod -aG sudo,"$GROUP" "$user"
  local home; home=$(getent passwd "$user" | cut -d: -f6)
  install -d -m 700 -o "$user" -g "$user" "$home/.ssh"
  touch "$home/.ssh/authorized_keys"
  grep -qxF "$key" "$home/.ssh/authorized_keys" || echo "$key" >> "$home/.ssh/authorized_keys"
  chown "$user:$user" "$home/.ssh/authorized_keys"
  chmod 600 "$home/.ssh/authorized_keys"
  echo "OK: $user can SSH with that key and use sudo (with their password)."
  echo "Test from their laptop:  ssh $user@<server-ip>   then   sudo whoami"
}

cmd_remove() {
  local user=$1
  id "$user" >/dev/null 2>&1 || { echo "No such user"; exit 1; }
  pkill -KILL -u "$user" 2>/dev/null || true
  deluser --remove-home "$user"
  echo "Removed $user"
}

cmd_harden() {
  # Refuse if nobody could log in afterwards
  local ok=0
  for u in $(getent group sudo | cut -d: -f4 | tr ',' ' '); do
    local home; home=$(getent passwd "$u" | cut -d: -f6)
    [[ -s $home/.ssh/authorized_keys ]] && ok=1
  done
  if [[ $ok -eq 0 ]]; then
    echo "No sudo user with an SSH key yet. Run 'add' first, test the login, then harden."
    exit 1
  fi
  cat > /etc/ssh/sshd_config.d/90-ctf.conf <<'CONF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
CONF
  sshd -t
  systemctl restart ssh
  echo "SSH: keys only, no root login."
  echo "KEEP THIS SESSION OPEN and test a fresh login in another terminal first."
}

cmd_list() {
  echo "sudo:    $(getent group sudo | cut -d: -f4)"
  echo "$GROUP: $(getent group "$GROUP" | cut -d: -f4 || true)"
}

case "${1:-}" in
  add)        [[ $# -eq 3 ]] || { echo "usage: $0 add <user> \"<ssh-pubkey>\""; exit 1; }; cmd_add "$2" "$3" ;;
  remove)     [[ $# -eq 2 ]] || { echo "usage: $0 remove <user>"; exit 1; }; cmd_remove "$2" ;;
  harden-ssh) cmd_harden ;;
  list)       cmd_list ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
