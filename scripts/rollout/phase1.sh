#!/bin/bash
# scripts/rollout/phase1.sh
# Phase 1: 10% Rollout

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Import common functions
source "$SCRIPT_DIR/common-functions.sh"

PHASE_NUMBER=1
ROLLOUT_PERCENT=0.10
MONITORING_DURATION=4h

main() {
    cat << 'EOF'

╔══════════════════════════════════════════════════════════╗
║                                                          ║
║       Phase 1: 10% Event-Driven Rollout                 ║
║                                                          ║
║  This will enable Event-Driven mode for 10% of traffic  ║
║  Monitoring: 4 hours intensive                          ║
║  Auto-rollback: Enabled on failure                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

EOF

    log "Starting Phase 1 deployment..."
    echo ""

    # Step 1: Pre-flight checks
    section "Step 1: Pre-Flight Checks"
    if ! "$SCRIPT_DIR/preflight-checks.sh"; then
        error "Pre-flight checks failed. Aborting rollout."
        exit 1
    fi

    # Step 2: Confirm with user
    echo ""
    if ! confirm "Proceed with Phase 1 (10% rollout)?" "n"; then
        warn "Rollout cancelled by user"
        exit 0
    fi

    # Step 3: Update configuration
    section "Step 2: Update Configuration"
    log "Setting rollout to ${ROLLOUT_PERCENT}% (Event-Driven enabled)..."
    update_rollout_config "$ROLLOUT_PERCENT"
    echo ""
    log "Configuration updated successfully"

    # Step 4: Deploy (restart Worker)
    section "Step 3: Deploy Worker"
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

    if ! check_service_health "Worker" "http://localhost:${WORKER_PORT:-9191}/health"; then
        error "Worker is not healthy after restart"
        error "Rolling back..."
        "$PROJECT_ROOT/scripts/rollback-event-driven.sh"
        exit 1
    fi

    log "Worker is healthy"

    # Step 5: Monitor
    section "Step 4: Monitoring (${MONITORING_DURATION})"
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

    # Step 6: Success
    section "Phase 1 Completed! ✅"
    echo ""
    log "✅ Phase 1 (10% rollout) completed successfully!"
    echo ""
    log "Next Steps:"
    log "  1. Review metrics on dashboard: http://localhost:3001/d/ab-testing"
    log "  2. Verify Go/No-Go criteria: ./scripts/rollout/check-metrics.sh --phase=1"
    log "  3. If all good, proceed: ./scripts/rollout/phase2.sh"
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
