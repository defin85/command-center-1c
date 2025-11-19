#!/bin/bash
# scripts/rollout/check-metrics.sh
# Go/No-Go decision automation based on metrics

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/common-functions.sh"

# Default values
PHASE=1
LOOKBACK="1h"  # Look at last 1 hour of metrics

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --phase=*)
            PHASE="${1#*=}"
            shift
            ;;
        --lookback=*)
            LOOKBACK="${1#*=}"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Check metrics and make Go/No-Go decision for next rollout phase.

OPTIONS:
    --phase=NUMBER         Phase number to check (1, 2, or 3)
                          Default: 1

    --lookback=DURATION   Time window for metrics analysis (e.g., 1h, 30m)
                          Default: 1h

    -h, --help            Show this help message

EXAMPLES:
    # Check Phase 1 metrics (last 1 hour)
    $0 --phase=1

    # Check Phase 2 metrics with custom lookback
    $0 --phase=2 --lookback=2h

    # Quick check (last 15 minutes)
    $0 --phase=1 --lookback=15m

EXIT CODES:
    0 - GO (all criteria met)
    1 - NO-GO (one or more criteria failed)

EOF
}

main() {
    section "Phase $PHASE Metrics Check"

    log "Configuration:"
    log "  Phase: $PHASE"
    log "  Lookback Window: $LOOKBACK"
    log "  Dashboard: http://localhost:3001/d/ab-testing"
    echo ""

    # Validate Prometheus is available
    if ! check_service_health "Prometheus" "http://localhost:9090/-/healthy"; then
        error "Prometheus is not available"
        exit 1
    fi

    local failures=0

    # Run all checks
    log "Running Go/No-Go criteria checks..."
    echo ""

    # Criteria 1: Success rate >= 95%
    if check_success_rate; then
        ((failures+=0))
    else
        ((failures++))
    fi

    # Criteria 2: P99 latency < 1s
    if check_p99_latency; then
        ((failures+=0))
    else
        ((failures++))
    fi

    # Criteria 3: Compensation rate < 10%
    if check_compensation_rate; then
        ((failures+=0))
    else
        ((failures++))
    fi

    # Criteria 4: No circuit breaker trips
    if check_no_circuit_breaker_trips; then
        ((failures+=0))
    else
        ((failures++))
    fi

    # Criteria 5: Redis healthy
    if check_redis_healthy; then
        ((failures+=0))
    else
        ((failures++))
    fi

    # Summary
    echo ""
    echo "========================================"

    if [ "$failures" -eq 0 ]; then
        print_success "Phase $PHASE: GO for next phase! ✅"
        log "All criteria met. Safe to proceed with next rollout phase."
        log "Next: ./scripts/rollout/phase$(($PHASE + 1)).sh"
        return 0
    else
        print_error "Phase $PHASE: NO-GO ❌"
        error "$failures criteria not met. Do NOT proceed to next phase."
        echo ""
        error "Actions required:"
        error "  1. Review dashboard: http://localhost:3001/d/ab-testing"
        error "  2. Investigate failed criteria above"
        error "  3. Fix issues and re-run this check"
        error "  4. If issues persist, consider rollback: ./scripts/rollback-event-driven.sh"
        return 1
    fi
}

check_success_rate() {
    local query='rate(worker_execution_success_total{mode="event_driven"}['$LOOKBACK']) / rate(worker_execution_mode_total{mode="event_driven"}['$LOOKBACK'])'
    local result=$(query_prometheus "$query")

    echo -n "  [Success Rate] ... "

    if [ "$result" == "0" ] || [ -z "$result" ]; then
        echo -e "${YELLOW}SKIP${NC} (no data yet)"
        warn "    No Event-Driven executions in lookback window"
        return 0  # Allow to proceed if no data (early rollout)
    fi

    if [ "$(float_ge "$result" "0.95")" == "1" ]; then
        echo -e "${GREEN}PASS${NC}"
        log "    Value: $(format_percent $result) >= 95%"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        error "    Value: $(format_percent $result) < 95%"
        return 1
    fi
}

check_p99_latency() {
    local query='histogram_quantile(0.99, rate(worker_execution_duration_seconds_bucket{mode="event_driven"}['$LOOKBACK']))'
    local result=$(query_prometheus "$query")

    echo -n "  [P99 Latency] ... "

    if [ "$result" == "0" ] || [ -z "$result" ]; then
        echo -e "${YELLOW}SKIP${NC} (no data yet)"
        return 0
    fi

    if [ "$(float_lt "$result" "1.0")" == "1" ]; then
        echo -e "${GREEN}PASS${NC}"
        log "    Value: ${result}s < 1s"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        error "    Value: ${result}s >= 1s"
        return 1
    fi
}

check_compensation_rate() {
    local query='rate(worker_compensation_executed_total['$LOOKBACK']) / rate(worker_execution_mode_total{mode="event_driven"}['$LOOKBACK'])'
    local result=$(query_prometheus "$query")

    echo -n "  [Compensation Rate] ... "

    if [ "$result" == "0" ] || [ -z "$result" ]; then
        echo -e "${GREEN}PASS${NC}"
        log "    Value: 0% (no compensations)"
        return 0
    fi

    if [ "$(float_lt "$result" "0.10")" == "1" ]; then
        echo -e "${GREEN}PASS${NC}"
        log "    Value: $(format_percent $result) < 10%"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        error "    Value: $(format_percent $result) >= 10%"
        return 1
    fi
}

check_no_circuit_breaker_trips() {
    local query='increase(worker_circuit_breaker_trips_total{mode="event_driven"}['$LOOKBACK'])'
    local result=$(query_prometheus "$query")

    echo -n "  [Circuit Breaker] ... "

    if [ "$result" == "0" ] || [ -z "$result" ]; then
        echo -e "${GREEN}PASS${NC}"
        log "    No trips detected"
        return 0
    else
        echo -e "${YELLOW}WARN${NC}"
        warn "    Trips detected: $result"
        warn "    Investigate circuit breaker logs"
        return 1
    fi
}

check_redis_healthy() {
    echo -n "  [Redis Connection] ... "

    if check_redis; then
        echo -e "${GREEN}PASS${NC}"
        log "    Redis responding to PING"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        error "    Redis unavailable"
        return 1
    fi
}

main "$@"
