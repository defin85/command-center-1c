#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$PROJECT_ROOT/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env.local"
  set +a
fi

WORKER_PORT="${WORKER_PORT:-9191}"
WORKER_WORKFLOWS_PORT="${WORKER_WORKFLOWS_METRICS_PORT:-9092}"
FRONTEND_PORT="${FRONTEND_PORT:-15173}"
ORCHESTRATOR_PORT="${ORCHESTRATOR_PORT:-8200}"
API_GATEWAY_PORT="${API_GATEWAY_PORT:-8180}"

declare -A PID_FILES=(
  ["orchestrator"]="$PROJECT_ROOT/pids/orchestrator.pid"
  ["event-subscriber"]="$PROJECT_ROOT/pids/event-subscriber.pid"
  ["api-gateway"]="$PROJECT_ROOT/pids/api-gateway.pid"
  ["worker"]="$PROJECT_ROOT/pids/worker.pid"
  ["worker-workflows"]="$PROJECT_ROOT/pids/worker-workflows.pid"
  ["frontend"]="$PROJECT_ROOT/pids/frontend.pid"
)

declare -A URLS=(
  ["orchestrator"]="http://localhost:${ORCHESTRATOR_PORT}/health"
  ["api-gateway"]="http://localhost:${API_GATEWAY_PORT}/health"
  ["worker"]="http://localhost:${WORKER_PORT}/health"
  ["worker-workflows"]="http://localhost:${WORKER_WORKFLOWS_PORT}/health"
  ["frontend"]="http://localhost:${FRONTEND_PORT}"
)

check_pid() {
  local runtime="$1"
  local pid_file="${PID_FILES[$runtime]:-}"
  if [[ -z "$pid_file" || ! -f "$pid_file" ]]; then
    echo "down"
    return
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "up(pid=$pid)"
  else
    echo "down"
  fi
}

check_http() {
  local runtime="$1"
  local url="${URLS[$runtime]:-}"
  if [[ -z "$url" ]]; then
    echo "n/a"
    return
  fi
  local code
  code="$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" --max-time 4 "$url" 2>/dev/null || true)"
  if [[ "$code" == "200" ]]; then
    echo "up(http=$code)"
  elif [[ -n "$code" && "$code" != "000" ]]; then
    echo "warn(http=$code)"
  else
    echo "down"
  fi
}

probe_one() {
  local runtime="$1"
  printf "%-16s proc=%-14s http=%s\n" "$runtime" "$(check_pid "$runtime")" "$(check_http "$runtime")"
}

main() {
  local target="${1:-all}"
  case "$target" in
    all)
      probe_one orchestrator
      probe_one event-subscriber
      probe_one api-gateway
      probe_one worker
      probe_one worker-workflows
      probe_one frontend
      ;;
    orchestrator|event-subscriber|api-gateway|worker|worker-workflows|frontend)
      probe_one "$target"
      ;;
    *)
      echo "Usage: $0 [all|orchestrator|event-subscriber|api-gateway|worker|worker-workflows|frontend]" >&2
      exit 1
      ;;
  esac
}

main "$@"

