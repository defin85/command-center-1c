#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$PROJECT_ROOT/debug/_cc1c_api.sh"

if [[ ! -f "$HELPER" ]]; then
  echo "Missing helper script: $HELPER" >&2
  exit 1
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  ./debug/query-ui-timeline.sh [key=value ...]

Required environment:
  CC1C_TENANT_ID=<tenant-uuid>
  CC1C_ACCESS_TOKEN=<jwt>

Optional environment:
  CC1C_BASE_URL=http://localhost:15173
  CC1C_UI_USER=<username>
  CC1C_UI_PASSWORD=<password>

Examples:
  ./debug/query-ui-timeline.sh request_id=req-123 limit=200
  ./debug/query-ui-timeline.sh trace_id=trace-abc123
  ./debug/query-ui-timeline.sh session_id=session-42 start=2026-04-19T12:00:00Z
USAGE
  exit 0
fi

# shellcheck disable=SC1091
source "$HELPER"

cc1c_api_get_json "/api/v2/ui/incident-telemetry/timeline/" 1 "$@"
