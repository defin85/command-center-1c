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
  ./debug/query-ui-incidents.sh [key=value ...]

Required environment:
  CC1C_TENANT_ID=<tenant-uuid>
  CC1C_ACCESS_TOKEN=<jwt>

Optional environment:
  CC1C_BASE_URL=http://localhost:15173
  CC1C_UI_USER=<username>
  CC1C_UI_PASSWORD=<password>

Examples:
  ./debug/query-ui-incidents.sh limit=20 route_path=/pools/runs
  ./debug/query-ui-incidents.sh actor_username=admin ui_action_id=uia-123
  ./debug/query-ui-incidents.sh trace_id=trace-abc123 start=2026-04-19T12:00:00Z
USAGE
  exit 0
fi

# shellcheck disable=SC1091
source "$HELPER"

cc1c_api_get_json "/api/v2/ui/incident-telemetry/incidents/" 1 "$@"
