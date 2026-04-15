#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy/install-server-deployer.sh --host <ip> --port <port> --user <ssh-user> --ssh-pass <password>

Installs:
  - /usr/local/bin/cc1c-deploy (native activation script)
  - /usr/local/bin/cc1c-upload-release (root-owned upload helper)
  - sudoers rule to allow passwordless run of cc1c-deploy for the SSH user
  - temporary no-domain Django setting in /etc/command-center-1c/env.production
EOF
}

HOST=""
PORT=""
USER_NAME=""
SSH_PASS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --ssh-pass) SSH_PASS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$PORT" || -z "$USER_NAME" || -z "$SSH_PASS" ]]; then
  usage
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass is required."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ACTIVATE_SCRIPT="$SCRIPT_DIR/native-activate.sh"
LOCAL_UPLOAD_SCRIPT="$SCRIPT_DIR/upload-release.sh"

if [[ ! -f "$LOCAL_ACTIVATE_SCRIPT" ]]; then
  echo "File not found: $LOCAL_ACTIVATE_SCRIPT"
  exit 1
fi

if [[ ! -f "$LOCAL_UPLOAD_SCRIPT" ]]; then
  echo "File not found: $LOCAL_UPLOAD_SCRIPT"
  exit 1
fi

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_ACTIVATE_SCRIPT" "$USER_NAME@$HOST:/tmp/cc1c-deploy"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_UPLOAD_SCRIPT" "$USER_NAME@$HOST:/tmp/cc1c-upload-release"

sshpass -p "$SSH_PASS" ssh -p "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$USER_NAME@$HOST" "bash -lc '
set -euo pipefail
printf \"%s\n\" \"$SSH_PASS\" | sudo -S -k install -o root -g root -m 750 /tmp/cc1c-deploy /usr/local/bin/cc1c-deploy
printf \"%s\n\" \"$SSH_PASS\" | sudo -S -k install -o root -g root -m 750 /tmp/cc1c-upload-release /usr/local/bin/cc1c-upload-release
printf \"%s\n\" \"$SSH_PASS\" | sudo -S sh -c \"cat > /etc/sudoers.d/cc1c-deploy <<SUDOERS
$USER_NAME ALL=(root) NOPASSWD: /usr/local/bin/cc1c-deploy, /usr/local/bin/cc1c-upload-release
SUDOERS\"
printf \"%s\n\" \"$SSH_PASS\" | sudo -S chmod 440 /etc/sudoers.d/cc1c-deploy
printf \"%s\n\" \"$SSH_PASS\" | sudo -S visudo -cf /etc/sudoers.d/cc1c-deploy
if printf \"%s\n\" \"$SSH_PASS\" | sudo -S test -f /etc/command-center-1c/env.production; then
  printf \"%s\n\" \"$SSH_PASS\" | sudo -S sed -i \"s/^DJANGO_SETTINGS_MODULE=.*/DJANGO_SETTINGS_MODULE=config.settings.development/\" /etc/command-center-1c/env.production || true
fi
rm -f /tmp/cc1c-deploy
rm -f /tmp/cc1c-upload-release
'"

echo "Server deployer installed successfully."
