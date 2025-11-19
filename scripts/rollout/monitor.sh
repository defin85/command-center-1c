#!/bin/bash
# scripts/rollout/monitor.sh
# Automated monitoring with auto-rollback on failure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/common-functions.sh"

# ===== CONFIGURATION CONSTANTS =====
readonly DEFAULT_CHECK_INTERVAL=60      # seconds - balance between responsiveness and load
readonly DEFAULT_MAX_FAILURES=3         # consecutive failures before rollback
readonly SUMMARY_INTERVAL=5             # show summary every N checks
readonly SUCCESS_RATE_THRESHOLD=0.95    # 95% success rate required
readonly LATENCY_THRESHOLD_SEC=1.0      # P99 latency threshold (seconds)
readonly COMPENSATION_THRESHOLD=0.10    # 10% compensation rate threshold

# Default values (can be overridden by CLI arguments)
DURATION="4h"
THRESHOLD=$SUCCESS_RATE_THRESHOLD
AUTO_ROLLBACK=false
CHECK_INTERVAL=$DEFAULT_CHECK_INTERVAL
MAX_CONSECUTIVE_FAILURES=$DEFAULT_MAX_FAILURES

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration=*)
            DURATION="${1#*=}"
            shift
            ;;
        --threshold=*)
            THRESHOLD="${1#*=}"
            shift
            ;;
        --auto-rollback)
            AUTO_ROLLBACK=true
            shift
            ;;
        --check-interval=*)
            CHECK_INTERVAL="${1#*=}"
            shift
            ;;
        --max-failures=*)
            MAX_CONSECUTIVE_FAILURES="${1#*=}"
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

Automated monitoring with auto-rollback capability.

OPTIONS:
    --duration=DURATION          Monitoring duration (e.g., 4h, 30m, 1d)
                                 Use 'continuous' for indefinite monitoring
                                 Default: 4h

    --threshold=FLOAT            Success rate threshold (0.0-1.0)
                                 Default: 0.95 (95%)

    --auto-rollback              Enable automatic rollback on failure
                                 Default: disabled

    --check-interval=SECONDS     Time between health checks
                                 Default: 60

    --max-failures=COUNT         Max consecutive failures before rollback
                                 Default: 3

    -h, --help                   Show this help message

EXAMPLES:
    # Monitor for 4 hours with auto-rollback
    $0 --duration=4h --threshold=0.95 --auto-rollback

    # Monitor continuously (manual intervention required)
    $0 --duration=continuous --check-interval=30

    # Custom threshold and failure tolerance
    $0 --duration=2h --threshold=0.98 --max-failures=5 --auto-rollback

EOF
}

main() {
    section "Starting Monitoring"

    log "Configuration:"
    log "  Duration: $DURATION"
    log "  Success Rate Threshold: $(format_percent $THRESHOLD)"
    log "  Auto-Rollback: $AUTO_ROLLBACK"
    log "  Check Interval: ${CHECK_INTERVAL}s"
    log "  Max Consecutive Failures: $MAX_CONSECUTIVE_FAILURES"

    echo ""

    # Validate configuration
    if ! ensure_commands curl jq awk; then
        error "Missing required commands"
        exit 1
    fi

    # Convert duration to seconds
    local duration_seconds
    if [ "$DURATION" == "continuous" ]; then
        duration_seconds=999999999  # Very large number for continuous
        log "Monitoring: CONTINUOUS (until manually stopped)"
    else
        duration_seconds=$(duration_to_seconds "$DURATION")
        if [ $? -ne 0 ]; then
            error "Invalid duration format: $DURATION"
            exit 1
        fi
        log "Monitoring until: $(date -d "+${duration_seconds} seconds" +'%Y-%m-%d %H:%M:%S' 2>/dev/null || date -v+${duration_seconds}S +'%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "end time")"
    fi

    log "Dashboard: http://localhost:3001/d/ab-testing"
    log "Prometheus: http://localhost:9090"

    echo ""
    log "Starting monitoring loop..."
    echo ""

    local start_time=$(date +%s)
    local end_time=$((start_time + duration_seconds))
    local check_count=0
    local consecutive_failures=0
    local total_failures=0

    while [ "$(date +%s)" -lt "$end_time" ]; do
        ((check_count++))

        local current_time=$(date +'%H:%M:%S')
        local elapsed=$(($(date +%s) - start_time))
        local remaining=$((end_time - $(date +%s)))

        info "Check #$check_count at $current_time (Elapsed: $(seconds_to_duration $elapsed), Remaining: $(seconds_to_duration $remaining))"

        # Run metrics check
        if check_metrics_healthy; then
            # Success - reset failure counter
            if [ $consecutive_failures -gt 0 ]; then
                log "✅ Metrics recovered (Previous failures: $consecutive_failures)"
            else
                log "✅ Metrics healthy"
            fi
            consecutive_failures=0
        else
            # Failure
            ((consecutive_failures++))
            ((total_failures++))
            warn "⚠️  Metrics check failed (Consecutive failures: $consecutive_failures/$MAX_CONSECUTIVE_FAILURES)"

            # Check if we should rollback
            if $AUTO_ROLLBACK && [ "$consecutive_failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
                error "❌ Max consecutive failures reached!"
                echo ""
                error "Initiating automatic rollback..."
                echo ""

                if "$PROJECT_ROOT/scripts/rollback-event-driven.sh"; then
                    print_error "Rollback executed successfully"
                else
                    error "Rollback failed! Manual intervention required!"
                fi

                return 1
            fi
        fi

        # Print summary
        if [ $((check_count % SUMMARY_INTERVAL)) -eq 0 ]; then
            echo ""
            info "--- Summary (Checks: $check_count, Failures: $total_failures, Success Rate: $(awk -v total=$check_count -v fail=$total_failures 'BEGIN {printf "%.1f%%", (total - fail) * 100 / total}')) ---"
            echo ""
        fi

        # Sleep until next check
        if [ "$(date +%s)" -lt "$end_time" ]; then
            sleep "$CHECK_INTERVAL"
        fi
    done

    echo ""
    log "✅ Monitoring period completed"
    echo ""
    log "Final Statistics:"
    log "  Total Checks: $check_count"
    log "  Total Failures: $total_failures"
    log "  Success Rate: $(awk -v total=$check_count -v fail=$total_failures 'BEGIN {printf "%.1f%%", (total - fail) * 100 / total}')"
    echo ""

    return 0
}

check_metrics_healthy() {
    local failures=0

    # Check 1: Success rate >= threshold
    local success_rate=$(get_success_rate)
    if [ "$(float_ge "$success_rate" "$THRESHOLD")" == "1" ]; then
        debug "  ✓ Success rate: $(format_percent $success_rate)"
    else
        warn "  ✗ Success rate too low: $(format_percent $success_rate) < $(format_percent $THRESHOLD)"
        ((failures++))
    fi

    # Check 2: P99 latency < threshold
    local p99_latency=$(get_p99_latency)
    if [ "$(float_lt "$p99_latency" "$LATENCY_THRESHOLD_SEC")" == "1" ]; then
        debug "  ✓ P99 latency: ${p99_latency}s"
    else
        warn "  ✗ P99 latency too high: ${p99_latency}s >= ${LATENCY_THRESHOLD_SEC}s"
        ((failures++))
    fi

    # Check 3: Compensation rate < threshold
    local comp_rate=$(get_compensation_rate)
    if [ "$(float_lt "$comp_rate" "$COMPENSATION_THRESHOLD")" == "1" ]; then
        debug "  ✓ Compensation rate: $(format_percent $comp_rate)"
    else
        warn "  ✗ Compensation rate too high: $(format_percent $comp_rate) >= $(format_percent $COMPENSATION_THRESHOLD)"
        ((failures++))
    fi

    # Check 4: Worker service healthy
    if check_service_health "Worker" "http://localhost:9091/health"; then
        debug "  ✓ Worker service healthy"
    else
        warn "  ✗ Worker service unavailable"
        ((failures++))
    fi

    return $failures
}

get_success_rate() {
    local query='rate(worker_execution_success_total{mode="event_driven"}[5m]) / rate(worker_execution_mode_total{mode="event_driven"}[5m])'
    query_prometheus "$query"
}

get_p99_latency() {
    local query='histogram_quantile(0.99, rate(worker_execution_duration_seconds_bucket{mode="event_driven"}[5m]))'
    query_prometheus "$query"
}

get_compensation_rate() {
    local query='rate(worker_compensation_executed_total[5m]) / rate(worker_execution_mode_total{mode="event_driven"}[5m])'
    query_prometheus "$query"
}

main "$@"
