#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy/install-server-deployer.sh --host <ip> --port <port> --user <ssh-user> --ssh-pass <password>

Installs:
  - /usr/local/bin/cc1c-deploy (native activation script)
  - /usr/local/bin/cc1c-upload-release (root-owned upload helper)
  - server disk/log guard config for journald, rsyslog, logrotate and ClickHouse
  - sudoers rule to allow passwordless run of cc1c-deploy for the SSH user
  - native no-domain Django setting in /etc/command-center-1c/env.production
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
LOCAL_SERVER_CONFIG_DIR="$SCRIPT_DIR/server-config"
LOCAL_JOURNALD_DROPIN="$LOCAL_SERVER_CONFIG_DIR/systemd/journald.conf.d/99-cc1c-disk-guard.conf"
LOCAL_LOGROTATE_TIMER_DROPIN="$LOCAL_SERVER_CONFIG_DIR/systemd/logrotate.timer.d/override.conf"
LOCAL_RSYSLOG_LOGROTATE="$LOCAL_SERVER_CONFIG_DIR/logrotate/rsyslog"
LOCAL_CLICKHOUSE_LOGGING="$LOCAL_SERVER_CONFIG_DIR/clickhouse-server/config.d/cc1c-logging.xml"
LOCAL_CLICKHOUSE_SERVICE_OVERRIDE="$LOCAL_SERVER_CONFIG_DIR/systemd/clickhouse-server.service.d/override.conf"

if [[ ! -f "$LOCAL_ACTIVATE_SCRIPT" ]]; then
  echo "File not found: $LOCAL_ACTIVATE_SCRIPT"
  exit 1
fi

if [[ ! -f "$LOCAL_UPLOAD_SCRIPT" ]]; then
  echo "File not found: $LOCAL_UPLOAD_SCRIPT"
  exit 1
fi

for required_file in \
  "$LOCAL_JOURNALD_DROPIN" \
  "$LOCAL_LOGROTATE_TIMER_DROPIN" \
  "$LOCAL_RSYSLOG_LOGROTATE" \
  "$LOCAL_CLICKHOUSE_LOGGING" \
  "$LOCAL_CLICKHOUSE_SERVICE_OVERRIDE"; do
  if [[ ! -f "$required_file" ]]; then
    echo "File not found: $required_file"
    exit 1
  fi
done

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_ACTIVATE_SCRIPT" "$USER_NAME@$HOST:/tmp/cc1c-deploy"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_UPLOAD_SCRIPT" "$USER_NAME@$HOST:/tmp/cc1c-upload-release"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_JOURNALD_DROPIN" "$USER_NAME@$HOST:/tmp/cc1c-journald.conf"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_LOGROTATE_TIMER_DROPIN" "$USER_NAME@$HOST:/tmp/cc1c-logrotate.timer.override"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_RSYSLOG_LOGROTATE" "$USER_NAME@$HOST:/tmp/cc1c-rsyslog.logrotate"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_CLICKHOUSE_LOGGING" "$USER_NAME@$HOST:/tmp/cc1c-clickhouse-logging.xml"

sshpass -p "$SSH_PASS" scp -P "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$LOCAL_CLICKHOUSE_SERVICE_OVERRIDE" "$USER_NAME@$HOST:/tmp/cc1c-clickhouse.override"

sshpass -p "$SSH_PASS" ssh -p "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$USER_NAME@$HOST" "bash -lc '
set -euo pipefail
printf \"%s\n\" \"$SSH_PASS\" | sudo -S -k install -o root -g root -m 750 /tmp/cc1c-deploy /usr/local/bin/cc1c-deploy
printf \"%s\n\" \"$SSH_PASS\" | sudo -S -k install -o root -g root -m 750 /tmp/cc1c-upload-release /usr/local/bin/cc1c-upload-release
printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -d -o root -g root -m 755 /etc/systemd/journald.conf.d /etc/systemd/system/logrotate.timer.d
printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -o root -g root -m 644 /tmp/cc1c-journald.conf /etc/systemd/journald.conf.d/99-cc1c-disk-guard.conf
printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -o root -g root -m 644 /tmp/cc1c-logrotate.timer.override /etc/systemd/system/logrotate.timer.d/override.conf
printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -o root -g root -m 644 /tmp/cc1c-rsyslog.logrotate /etc/logrotate.d/rsyslog
if printf \"%s\n\" \"$SSH_PASS\" | sudo -S test -d /etc/clickhouse-server; then
  printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -d -o root -g root -m 755 /etc/clickhouse-server/config.d /etc/systemd/system/clickhouse-server.service.d
  printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -o root -g root -m 644 /tmp/cc1c-clickhouse-logging.xml /etc/clickhouse-server/config.d/cc1c-logging.xml
  printf \"%s\n\" \"$SSH_PASS\" | sudo -S install -o root -g root -m 644 /tmp/cc1c-clickhouse.override /etc/systemd/system/clickhouse-server.service.d/override.conf
fi
printf \"%s\n\" \"$SSH_PASS\" | sudo -S sh -c \"cat > /etc/sudoers.d/cc1c-deploy <<SUDOERS
$USER_NAME ALL=(root) NOPASSWD: /usr/local/bin/cc1c-deploy, /usr/local/bin/cc1c-upload-release
SUDOERS\"
printf \"%s\n\" \"$SSH_PASS\" | sudo -S chmod 440 /etc/sudoers.d/cc1c-deploy
printf \"%s\n\" \"$SSH_PASS\" | sudo -S visudo -cf /etc/sudoers.d/cc1c-deploy
if printf \"%s\n\" \"$SSH_PASS\" | sudo -S test -f /etc/command-center-1c/env.production; then
  if printf \"%s\n\" \"$SSH_PASS\" | sudo -S grep -q \"^DJANGO_SETTINGS_MODULE=\" /etc/command-center-1c/env.production; then
    printf \"%s\n\" \"$SSH_PASS\" | sudo -S sed -i \"s/^DJANGO_SETTINGS_MODULE=.*/DJANGO_SETTINGS_MODULE=config.settings.native/\" /etc/command-center-1c/env.production
  else
    printf \"%s\n\" \"$SSH_PASS\" | sudo -S sh -c \"printf \\\"\\nDJANGO_SETTINGS_MODULE=config.settings.native\\n\\\" >> /etc/command-center-1c/env.production\"
  fi
fi
printf \"%s\n\" \"$SSH_PASS\" | sudo -S systemctl daemon-reload
printf \"%s\n\" \"$SSH_PASS\" | sudo -S systemctl restart logrotate.timer
printf \"%s\n\" \"$SSH_PASS\" | sudo -S systemctl restart rsyslog
printf \"%s\n\" \"$SSH_PASS\" | sudo -S systemctl restart systemd-journald
if printf \"%s\n\" \"$SSH_PASS\" | sudo -S systemctl cat clickhouse-server.service >/dev/null 2>&1; then
  printf \"%s\n\" \"$SSH_PASS\" | sudo -S systemctl restart clickhouse-server
fi
rm -f /tmp/cc1c-deploy
rm -f /tmp/cc1c-upload-release
rm -f /tmp/cc1c-journald.conf
rm -f /tmp/cc1c-logrotate.timer.override
rm -f /tmp/cc1c-rsyslog.logrotate
rm -f /tmp/cc1c-clickhouse-logging.xml
rm -f /tmp/cc1c-clickhouse.override
'"

echo "Server deployer installed successfully."
