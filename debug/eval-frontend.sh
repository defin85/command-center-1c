#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$PROJECT_ROOT/scripts/dev/chrome-debug.py"
START_SCRIPT="$PROJECT_ROOT/debug/start-chromium-cdp.sh"

CDP_PORT="${CDP_PORT:-9222}"
FRONTEND_TARGET_URL="${FRONTEND_TARGET_URL:-http://localhost:15173}"
CDP_PROFILE_DIR="${CDP_PROFILE_DIR:-/tmp/cc1c-cdp-profile}"
CDP_LOG_FILE="${CDP_LOG_FILE:-/tmp/cc1c-cdp.log}"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Missing script: $SCRIPT" >&2
  exit 1
fi

if [[ ! -x "$START_SCRIPT" ]]; then
  echo "Missing executable script: $START_SCRIPT" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  cat <<'USAGE' >&2
Usage:
  ./debug/eval-frontend.sh "<javascript expression>" [url-pattern]

Examples:
  ./debug/eval-frontend.sh "document.title"
  ./debug/eval-frontend.sh "window.location.href" "localhost:15173"
USAGE
  exit 1
fi

EXPR="$1"
URL_PATTERN="${2:-localhost:15173}"

"$START_SCRIPT" "$CDP_PORT" "$FRONTEND_TARGET_URL" "$CDP_PROFILE_DIR" "$CDP_LOG_FILE" >/dev/null
python3 "$SCRIPT" --url "$URL_PATTERN" eval "$EXPR"
