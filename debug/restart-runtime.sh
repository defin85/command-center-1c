#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

runtime="${1:-}"
if [[ -z "$runtime" ]]; then
  echo "Usage: $0 <orchestrator|event-subscriber|api-gateway|worker|worker-workflows|frontend>" >&2
  exit 1
fi

case "$runtime" in
  orchestrator|event-subscriber|api-gateway|worker|worker-workflows|frontend)
    ;;
  *)
    echo "Unknown runtime: $runtime" >&2
    exit 1
    ;;
esac

cd "$PROJECT_ROOT"
./scripts/dev/restart.sh "$runtime"
./debug/probe.sh "$runtime"

