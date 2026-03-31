#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <release-archive.tar.gz> <release-id>"
  exit 1
fi

ARCHIVE_PATH="$1"
RELEASE_ID="$2"

BASE_DIR="/opt/command-center-1c"
RELEASES_DIR="$BASE_DIR/releases"
SHARED_DIR="$BASE_DIR/shared"
SHARED_VENVS_DIR="$SHARED_DIR/venvs"
CURRENT_LINK="$BASE_DIR/current"
ENV_FILE="/etc/command-center-1c/env.production"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_ID"
WHEELHOUSE_DIR="$RELEASE_DIR/orchestrator/wheelhouse"
PYTHON_BIN="${CC1C_PYTHON_BIN:-/usr/bin/python3.12}"
REQUIREMENTS_FILE="$RELEASE_DIR/orchestrator/requirements.txt"
REQUIREMENTS_HASH=""
TARGET_VENV_DIR=""

REQUIRED_FILES=(
  "bin/cc1c-api-gateway"
  "bin/cc1c-worker"
  "orchestrator/manage.py"
  "orchestrator/requirements.txt"
  "frontend/dist/index.html"
)

if [[ $EUID -ne 0 ]]; then
  echo "This script must run as root."
  exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive not found: $ARCHIVE_PATH"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE"
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PYTHON_BIN"
  echo "Install Python 3.12+ or set CC1C_PYTHON_BIN to a valid interpreter path."
  exit 1
fi

if id cc1c >/dev/null 2>&1; then
  true
else
  echo "System user cc1c does not exist."
  exit 1
fi

install -d -o cc1c -g cc1c -m 755 "$BASE_DIR" "$RELEASES_DIR"
install -d -o cc1c -g cc1c -m 755 "$SHARED_DIR" "$SHARED_VENVS_DIR"
install -d -o cc1c -g cc1c -m 750 "$RELEASE_DIR"
runuser -u cc1c -- tar -xzf "$ARCHIVE_PATH" -C "$RELEASE_DIR"

for rel_path in "${REQUIRED_FILES[@]}"; do
  if [[ ! -e "$RELEASE_DIR/$rel_path" ]]; then
    echo "Release archive missing required path: $rel_path"
    exit 1
  fi
done

chmod 750 "$RELEASE_DIR/bin/cc1c-api-gateway" "$RELEASE_DIR/bin/cc1c-worker"
chown -R cc1c:cc1c "$RELEASE_DIR"

REQUIREMENTS_HASH="$(sha256sum "$REQUIREMENTS_FILE" | awk '{print $1}')"
TARGET_VENV_DIR="$SHARED_VENVS_DIR/$REQUIREMENTS_HASH"

if [[ ! -d "$TARGET_VENV_DIR" ]]; then
  TEMP_VENV_DIR="$(mktemp -d "$SHARED_VENVS_DIR/.tmp-$REQUIREMENTS_HASH-XXXXXX")"
  chown cc1c:cc1c "$TEMP_VENV_DIR"
  runuser -u cc1c -- "$PYTHON_BIN" -m venv "$TEMP_VENV_DIR"

  if [[ -d "$WHEELHOUSE_DIR" ]] && [[ -n "$(find "$WHEELHOUSE_DIR" -mindepth 1 -print -quit)" ]]; then
    echo "Installing Python dependencies from bundled wheelhouse..."
    runuser -u cc1c -- "$TEMP_VENV_DIR/bin/pip" install \
      --disable-pip-version-check \
      --no-index \
      --find-links "$WHEELHOUSE_DIR" \
      -r "$REQUIREMENTS_FILE"
  else
    echo "Wheelhouse not found in release bundle, falling back to online pip install..."
    runuser -u cc1c -- "$TEMP_VENV_DIR/bin/pip" install \
      --disable-pip-version-check \
      -r "$REQUIREMENTS_FILE"
  fi

  mv "$TEMP_VENV_DIR" "$TARGET_VENV_DIR"
  chown -R cc1c:cc1c "$TARGET_VENV_DIR"
else
  echo "Reusing cached Python virtualenv for requirements hash $REQUIREMENTS_HASH"
fi

ln -sfn "$TARGET_VENV_DIR" "$RELEASE_DIR/orchestrator/venv"
chown -h cc1c:cc1c "$RELEASE_DIR/orchestrator/venv"

runuser -u cc1c -- /bin/bash -lc "set -a; source '$ENV_FILE'; set +a; cd '$RELEASE_DIR/orchestrator'; '$RELEASE_DIR/orchestrator/venv/bin/python' manage.py migrate --noinput"
runuser -u cc1c -- /bin/bash -lc "set -a; source '$ENV_FILE'; set +a; cd '$RELEASE_DIR/orchestrator'; '$RELEASE_DIR/orchestrator/venv/bin/python' manage.py collectstatic --noinput"

# Nginx must be able to traverse /opt/command-center-1c and read frontend assets.
chmod o+rx "$RELEASE_DIR" "$RELEASE_DIR/frontend" "$RELEASE_DIR/frontend/dist"
find "$RELEASE_DIR/frontend/dist" -type d -exec chmod o+rx {} +
find "$RELEASE_DIR/frontend/dist" -type f -exec chmod o+r {} +

ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
chown -h cc1c:cc1c "$CURRENT_LINK"

ln -sfn /etc/nginx/sites-available/command-center-1c.conf /etc/nginx/sites-enabled/command-center-1c.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

systemctl daemon-reload
systemctl enable cc1c-orchestrator.service cc1c-api-gateway.service cc1c-worker-ops.service cc1c-worker-workflows.service >/dev/null
systemctl restart cc1c-orchestrator.service cc1c-api-gateway.service cc1c-worker-ops.service cc1c-worker-workflows.service
systemctl is-active cc1c-orchestrator.service cc1c-api-gateway.service cc1c-worker-ops.service cc1c-worker-workflows.service >/dev/null

# Best-effort monitoring sync for native mode, so Prometheus/blackbox targets
# follow the same env as active release.
if [[ -x "$RELEASE_DIR/scripts/dev/sync-native-monitoring.sh" ]]; then
  if ! CC1C_ENV_FILE="$ENV_FILE" "$RELEASE_DIR/scripts/dev/sync-native-monitoring.sh" --env-file "$ENV_FILE" --strict; then
    echo "Warning: native monitoring sync failed (deployment continues)."
  fi
fi

echo "Release activated: $RELEASE_ID"
