#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-9222}"
TARGET_URL="${2:-http://localhost:15173}"
PROFILE_DIR="${3:-/tmp/cc1c-cdp-profile}"
LOG_FILE="${4:-/tmp/cc1c-cdp.log}"
HEADLESS="${HEADLESS:-1}"

choose_browser() {
  local browsers=("chromium" "chromium-browser" "google-chrome" "google-chrome-stable")
  local bin
  for bin in "${browsers[@]}"; do
    if command -v "$bin" >/dev/null 2>&1; then
      echo "$bin"
      return 0
    fi
  done
  return 1
}

cdp_available() {
  curl -fsS "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1
}

ensure_target_page() {
  local target_url="$1"
  if python3 - "$PORT" "$target_url" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

port = sys.argv[1]
target = sys.argv[2].lower()
with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as response:
    pages = json.load(response)
for page in pages:
    url = str(page.get("url") or "").lower()
    if target in url:
        raise SystemExit(0)
raise SystemExit(1)
PY
  then
    return 0
  fi

  local encoded_target
  encoded_target="$(python3 - "$target_url" <<'PY'
import sys
import urllib.parse

print(urllib.parse.quote(sys.argv[1], safe=':/?&=#%'))
PY
)"

  curl -fsS -X PUT "http://127.0.0.1:${PORT}/json/new?${encoded_target}" >/dev/null 2>&1 \
    || curl -fsS "http://127.0.0.1:${PORT}/json/new?${encoded_target}" >/dev/null 2>&1 \
    || true
}

if cdp_available; then
  ensure_target_page "$TARGET_URL"
  echo "CDP already available on 127.0.0.1:${PORT}"
  echo "Target: ${TARGET_URL}"
  exit 0
fi

BROWSER="$(choose_browser || true)"
if [[ -z "${BROWSER:-}" ]]; then
  echo "No Chromium/Chrome binary found in PATH." >&2
  exit 1
fi

mkdir -p "$PROFILE_DIR"

BROWSER_ARGS=(
  --remote-debugging-port="${PORT}"
  --no-first-run
  --no-default-browser-check
  --user-data-dir="$PROFILE_DIR"
)

if [[ "$HEADLESS" == "1" ]]; then
  BROWSER_ARGS+=(
    --headless=new
    --disable-gpu
    --disable-dev-shm-usage
    --no-sandbox
  )
fi

BROWSER_ARGS+=("$TARGET_URL")

if command -v setsid >/dev/null 2>&1; then
  nohup setsid "$BROWSER" "${BROWSER_ARGS[@]}" >"$LOG_FILE" 2>&1 &
else
  nohup "$BROWSER" "${BROWSER_ARGS[@]}" >"$LOG_FILE" 2>&1 &
fi

for _ in {1..30}; do
  if cdp_available; then
    ensure_target_page "$TARGET_URL"
    echo "CDP ready on 127.0.0.1:${PORT}"
    echo "Browser: ${BROWSER}"
    echo "Target: ${TARGET_URL}"
    echo "Profile: ${PROFILE_DIR}"
    echo "Log: ${LOG_FILE}"
    echo "Headless: ${HEADLESS}"
    exit 0
  fi
  sleep 1
done

echo "Failed to start Chromium CDP on port ${PORT}. Check ${LOG_FILE}" >&2
exit 1
