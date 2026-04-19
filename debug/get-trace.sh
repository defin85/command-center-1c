#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$PROJECT_ROOT/debug/_cc1c_api.sh"

if [[ ! -f "$HELPER" ]]; then
  echo "Missing helper script: $HELPER" >&2
  exit 1
fi

if [[ $# -lt 1 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  ./debug/get-trace.sh <trace-id>

Required environment:
  CC1C_ACCESS_TOKEN=<jwt>

Optional environment:
  CC1C_BASE_URL=http://localhost:15173
  CC1C_TENANT_ID=<tenant-uuid>
  CC1C_UI_USER=<username>
  CC1C_UI_PASSWORD=<password>

Example:
  ./debug/get-trace.sh trace-abc123
USAGE
  if [[ $# -lt 1 ]]; then
    exit 1
  fi
  exit 0
fi

TRACE_ID="$1"

# shellcheck disable=SC1091
source "$HELPER"

cc1c_api_get_json "/api/v2/tracing/traces/$TRACE_ID" 0
