#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL_SCRIPT="$PROJECT_ROOT/debug/eval-frontend.sh"
URL_PATTERN="${1:-localhost:15173}"

if [[ ! -x "$EVAL_SCRIPT" ]]; then
  echo "Missing executable script: $EVAL_SCRIPT" >&2
  exit 1
fi

"$EVAL_SCRIPT" "JSON.stringify(window.__CC1C_UI_JOURNAL__?.exportBundle() ?? null, null, 2)" "$URL_PATTERN"
