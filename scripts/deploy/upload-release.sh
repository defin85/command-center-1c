#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  /usr/local/bin/cc1c-upload-release </path/to/archive.tar.gz>

Reads a release archive from stdin and writes it atomically to a temporary
deployment path under /tmp or /var/tmp, then hands ownership back to the
deploy user so the regular cleanup step can remove it later.
EOF
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

ARCHIVE_PATH="$1"

case "$ARCHIVE_PATH" in
  /tmp/cc1c-release-*.tar.gz|/var/tmp/cc1c-release-*.tar.gz)
    ;;
  *)
    echo "Unsupported archive path: $ARCHIVE_PATH" >&2
    exit 1
    ;;
esac

DEPLOY_USER="${SUDO_USER:-}"
if [[ -z "$DEPLOY_USER" ]]; then
  echo "SUDO_USER is not set." >&2
  exit 1
fi

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  echo "Unknown deploy user: $DEPLOY_USER" >&2
  exit 1
fi

ARCHIVE_DIR="$(dirname "$ARCHIVE_PATH")"
TMP_PATH="${ARCHIVE_PATH}.partial.$$"

install -d -o root -g root -m 1777 "$ARCHIVE_DIR"
rm -f "$TMP_PATH"

cleanup() {
  rm -f "$TMP_PATH"
}
trap cleanup EXIT

cat > "$TMP_PATH"
chmod 600 "$TMP_PATH"
chown "$DEPLOY_USER:$DEPLOY_USER" "$TMP_PATH"
mv -f "$TMP_PATH" "$ARCHIVE_PATH"

trap - EXIT
