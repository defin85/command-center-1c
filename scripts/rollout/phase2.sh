#!/bin/bash
# scripts/rollout/phase2.sh
# Phase 2: 50% Rollout

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Import common functions
source "$SCRIPT_DIR/common-functions.sh"

PHASE_NUMBER=2
ROLLOUT_PERCENT=0.50
MONITORING_DURATION=4h

main() {
    cat << 'EOF'

╔══════════════════════════════════════════════════════════╗
║                                                          ║
║       Phase 2: 50% Event-Driven Rollout                 ║
║                                                          ║
║  This will enable Event-Driven mode for 50% of traffic  ║
║  Monitoring: 4 hours intensive                          ║
║  Auto-rollback: Enabled on failure                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

EOF

    log "Starting Phase 2 deployment..."
    echo ""

    # Step 1: Pre-flight checks
    section "Step 1: Pre-Flight Checks"
    if ! "$SCRIPT_DIR/preflight-checks.sh"; then
        error "Pre-flight checks failed. Aborting rollout."
        exit 1
    fi

    # Step 2: Check Phase 1 metrics
    section "Step 2: Validate Phase 1 Metrics"
    log "Checking if Phase 1 met Go/No-Go criteria..."
    echo ""
    if ! "$SCRIPT_DIR/check-metrics.sh" --phase=1; then
        error "Phase 1 metrics do not meet criteria. Aborting Phase 2."
        echo ""
        error "Actions:"
        error "  1. Review dashboard and fix issues"
        error "  2. Re-run: ./scripts/rollout/check-metrics.sh --phase=1"
        error "  3. Consider rollback if issues persist"
        exit 1
    fi

    # Step 3: Confirm with user
    echo ""
    if ! confirm "Phase 1 criteria met. Proceed with Phase 2 (50% rollout)?" "n"; then
        warn "Rollout cancelled by user"
        exit 0
    fi

    # Step 4: Update configuration
    section "Step 3: Update Configuration"
    log "Setting rollout to ${ROLLOUT_PERCENT}% (Event-Driven enabled)..."
    update_rollout_config "$ROLLOUT_PERCENT"
    echo ""
    log "Configuration updated successfully"

    # Step 5: Deploy (restart Worker)
    section "Step 4: Deploy Worker"
    log "Restarting Worker with new configuration..."
    if "$PROJECT_ROOT/scripts/dev/restart.sh" worker; then
        log "Worker restarted successfully"
    else
        error "Worker restart failed!"
        error "Rolling back..."
        "$PROJECT_ROOT/scripts/rollback-event-driven.sh"
        exit 1
    fi

    # Wait for Worker to be healthy
    echo ""
    log "Waiting for Worker to become healthy..."
    sleep 5

    if ! check_service_health "Worker" "http://localhost:9091/health"; then
        error "Worker is not healthy after restart"
        error "Rolling back..."
        "$PROJECT_ROOT/scripts/rollback-event-driven.sh"
        exit 1
    fi

    log "Worker is healthy"

    # Step 6: Monitor
    section "Step 5: Monitoring (${MONITORING_DURATION})"
    echo ""
    log "Dashboard: http://localhost:3001/d/ab-testing"
    log "Prometheus: http://localhost:9090"
    echo ""
    log "Starting automated monitoring with auto-rollback..."
    echo ""

    # Auto-monitor with rollback on failure
    if ! "$SCRIPT_DIR/monitor.sh" --duration="$MONITORING_DURATION" --threshold=0.95 --auto-rollback; then
        error "Monitoring detected issues. Rollback was executed."
        exit 1
    fi

    # Step 7: Success
    section "Phase 2 Completed! ✅"
    echo ""
    log "✅ Phase 2 (50% rollout) completed successfully!"
    echo ""
    log "Next Steps:"
    log "  1. Review metrics on dashboard: http://localhost:3001/d/ab-testing"
    log "  2. Verify Go/No-Go criteria: ./scripts/rollout/check-metrics.sh --phase=2"
    log "  3. If all good, proceed: ./scripts/rollout/phase3.sh"
    echo ""
}

update_rollout_config() {
    local percent="$1"

    # Backup current config
    backup_file "$PROJECT_ROOT/.env.local"

    # Update ENABLE_EVENT_DRIVEN=true
    update_env_var "ENABLE_EVENT_DRIVEN" "true"

    # Update ROLLOUT_PERCENT
    update_env_var "EVENT_DRIVEN_ROLLOUT_PERCENT" "$percent"

    log "Configuration:"
    log "  ENABLE_EVENT_DRIVEN=true"
    log "  EVENT_DRIVEN_ROLLOUT_PERCENT=$percent"
}

main "$@"
