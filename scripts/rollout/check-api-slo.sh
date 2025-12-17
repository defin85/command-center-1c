#!/bin/bash
# scripts/rollout/check-api-slo.sh
# Go/No-Go checks for API SLO (Gateway-side, user-perceived)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/common-functions.sh"

ensure_commands curl jq awk >/dev/null

LOOKBACK="30m"

while [[ $# -gt 0 ]]; do
    case $1 in
        --lookback=*)
            LOOKBACK="${1#*=}"
            shift
            ;;
        -h|--help)
            cat << EOF
Usage: $0 [OPTIONS]

Checks API SLO from Prometheus metrics (API Gateway).

OPTIONS:
  --lookback=DURATION   Prometheus range window (default: 30m)
  -h, --help            Show help

Examples:
  $0
  $0 --lookback=1h

EOF
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

require_prometheus() {
    if ! check_service_health "Prometheus" "http://localhost:9090/-/healthy"; then
        error "Prometheus is not available at http://localhost:9090"
        exit 1
    fi
}

check_scalar() {
    local label="$1"
    local query="$2"
    local comparator="$3" # lt/gt/ge/le
    local threshold="$4"

    echo -n "  [$label] ... "

    local result
    result=$(query_prometheus "$query")

    if [ "$result" == "0" ] || [ -z "$result" ]; then
        echo -e "${YELLOW}SKIP${NC} (no data yet)"
        return 0
    fi

    local ok=0
    case "$comparator" in
        lt) ok=$(float_lt "$result" "$threshold") ;;
        le) ok=$(float_le "$result" "$threshold") ;;
        gt) ok=$(float_gt "$result" "$threshold") ;;
        ge) ok=$(float_ge "$result" "$threshold") ;;
        *)
            error "Unknown comparator: $comparator"
            return 1
            ;;
    esac

    if [ "$ok" == "1" ]; then
        echo -e "${GREEN}PASS${NC}"
        log "    Value: $result"
        return 0
    fi

    echo -e "${RED}FAIL${NC}"
    error "    Value: $result"
    return 1
}

check_path_latency() {
    local path="$1"
    local quantile="$2"        # 0.95 / 0.99
    local threshold="$3"       # seconds
    local label="Latency p$(echo "$quantile" | sed 's/0\\.//') $path"

    local query="histogram_quantile($quantile, sum(rate(cc1c_request_duration_seconds_bucket{path=\\\"$path\\\"}[$LOOKBACK])) by (le))"
    check_scalar "$label" "$query" "lt" "$threshold"
}

check_path_availability() {
    local path="$1"
    local threshold="$2"
    local label="Availability $path"

    local query="1 - (sum(rate(cc1c_requests_total{path=\\\"$path\\\",status=~\\\"5..\\\"}[$LOOKBACK])) / (sum(rate(cc1c_requests_total{path=\\\"$path\\\"}[$LOOKBACK])) > 0 or vector(0)))"
    check_scalar "$label" "$query" "ge" "$threshold"
}

main() {
    section "API SLO Check"
    log "Lookback: $LOOKBACK"

    require_prometheus

    local failures=0

    # Global SLO (Gateway)
    check_scalar "Availability total (non-5xx)" \
        "1 - (sum(rate(cc1c_requests_total{status=~\\\"5..\\\"}[$LOOKBACK])) / (sum(rate(cc1c_requests_total[$LOOKBACK])) > 0 or vector(0)))" \
        "ge" "0.99" || ((failures++))

    check_scalar "Latency p95 total" \
        "histogram_quantile(0.95, sum(rate(cc1c_request_duration_seconds_bucket[$LOOKBACK])) by (le))" \
        "lt" "0.5" || ((failures++))

    check_scalar "Latency p99 total" \
        "histogram_quantile(0.99, sum(rate(cc1c_request_duration_seconds_bucket[$LOOKBACK])) by (le))" \
        "lt" "2.0" || ((failures++))

    # Critical SPA-primary actions (skip if no traffic)
    local critical_paths=(
        "/api/v2/operations/execute/"
        "/api/v2/extensions/batch-install/"
        "/api/v2/clusters/sync-cluster/"
        "/api/v2/workflows/execute-workflow/"
    )

    for p in "${critical_paths[@]}"; do
        check_path_availability "$p" "0.99" || ((failures++))
        check_path_latency "$p" "0.95" "1.0" || ((failures++))
        check_path_latency "$p" "0.99" "5.0" || ((failures++))
    done

    echo ""
    if [ "$failures" -eq 0 ]; then
        print_success "GO ✅ (API SLO meets targets)"
        return 0
    fi

    print_error "NO-GO ❌ ($failures checks failed)"
    error "Review Grafana dashboard: http://localhost:3001 (API SLO)"
    return 1
}

main "$@"
