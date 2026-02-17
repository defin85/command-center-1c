#!/bin/bash
# scripts/rollout/preflight-checks.sh
# Pre-flight validation before rollout deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$SCRIPT_DIR/common-functions.sh"

main() {
    section "Pre-Flight Checks"

    local failures=0

    # Check 1: All services healthy
    check "Services Health" check_services_health || ((failures++))

    # Check 2: Feature flags configured
    check "Feature Flags Config" check_feature_flags || ((failures++))

    # Check 3: Metrics collection working
    check "Metrics Collection" check_metrics_working || ((failures++))

    # Check 4: Rollback script exists
    check "Rollback Script" check_rollback_script || ((failures++))

    # Check 5: Monitoring alerts configured (optional, warn only)
    if ! check "Monitoring Alerts" check_alerts_configured; then
        warn "Monitoring alerts not configured (optional)"
    fi

    # Check 6: Backup exists
    check "Configuration Backup" check_backup_exists || ((failures++))

    # Check 7: PostgreSQL healthy
    check "PostgreSQL Connection" check_postgres || ((failures++))

    # Check 8: Redis healthy
    check "Redis Connection" check_redis || ((failures++))

    # Check 9: Required commands available
    check "Required Commands" check_required_commands || ((failures++))

    # Summary
    echo ""
    if [ "$failures" -eq 0 ]; then
        log "✅ All pre-flight checks passed!"
        return 0
    else
        error "❌ $failures pre-flight check(s) failed"
        echo ""
        error "Please fix the issues above before proceeding with rollout."
        return 1
    fi
}

check() {
    local name="$1"
    local func="$2"

    echo -n "  [$name] ... "

    if $func > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        return 1
    fi
}

check_services_health() {
    # Check Worker is running
    check_service_health "Worker" "http://localhost:${WORKER_PORT:-9191}/health"
}

check_feature_flags() {
    # Check .env.local exists and has required variables
    [ -f "$PROJECT_ROOT/.env.local" ] && \
    grep -q "ENABLE_EVENT_DRIVEN" "$PROJECT_ROOT/.env.local" && \
    grep -q "EVENT_DRIVEN_ROLLOUT_PERCENT" "$PROJECT_ROOT/.env.local"
}

check_metrics_working() {
    # Check Prometheus is responding
    check_service_health "Prometheus Health" "http://localhost:9090/-/healthy" && \
    check_service_health "Prometheus Query API" "http://localhost:9090/api/v1/query?query=up"
}

check_rollback_script() {
    [ -f "$PROJECT_ROOT/scripts/rollback-event-driven.sh" ] && \
    [ -x "$PROJECT_ROOT/scripts/rollback-event-driven.sh" ]
}

check_alerts_configured() {
    # Optional check - alerts may not be configured yet
    [ -f "$PROJECT_ROOT/infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml" ]
}

check_backup_exists() {
    if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
        return 1
    fi

    # Auto-create backup if doesn't exist
    if [ ! -f "$PROJECT_ROOT/.env.local.backup" ]; then
        cp "$PROJECT_ROOT/.env.local" "$PROJECT_ROOT/.env.local.backup"
        debug "Created initial backup: .env.local.backup"
    fi

    return 0
}

check_required_commands() {
    ensure_commands curl jq awk sed grep docker
}

main "$@"
