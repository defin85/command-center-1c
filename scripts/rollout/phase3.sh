#!/bin/bash
# scripts/rollout/phase3.sh
# Phase 3: 100% Rollout (FINAL!)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Import common functions
source "$SCRIPT_DIR/common-functions.sh"

PHASE_NUMBER=3
ROLLOUT_PERCENT=1.0
MONITORING_DURATION=24h  # Longer monitoring for final phase

main() {
    cat << 'EOF'

╔══════════════════════════════════════════════════════════╗
║                                                          ║
║       Phase 3: 100% Event-Driven Rollout (FINAL!)       ║
║                                                          ║
║  This will enable Event-Driven mode for ALL traffic     ║
║  Monitoring: 24 hours continuous                        ║
║  Auto-rollback: Enabled on failure                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

EOF

    log "Starting Phase 3 deployment (FINAL PHASE)..."
    echo ""

    # Step 1: Pre-flight checks
    section "Step 1: Pre-Flight Checks"
    if ! "$SCRIPT_DIR/preflight-checks.sh"; then
        error "Pre-flight checks failed. Aborting rollout."
        exit 1
    fi

    # Step 2: Check Phase 2 metrics
    section "Step 2: Validate Phase 2 Metrics"
    log "Checking if Phase 2 met Go/No-Go criteria..."
    echo ""
    if ! "$SCRIPT_DIR/check-metrics.sh" --phase=2; then
        error "Phase 2 metrics do not meet criteria. Aborting Phase 3."
        echo ""
        error "Actions:"
        error "  1. Review dashboard and fix issues"
        error "  2. Re-run: ./scripts/rollout/check-metrics.sh --phase=2"
        error "  3. Consider rollback if issues persist"
        exit 1
    fi

    # Step 3: Confirm with user (FINAL confirmation)
    echo ""
    warn "⚠️  FINAL PHASE: This will enable Event-Driven for 100% of traffic!"
    echo ""
    if ! confirm "Phase 2 criteria met. Proceed with Phase 3 (100% rollout)?" "n"; then
        warn "Rollout cancelled by user"
        exit 0
    fi

    # Step 4: Update configuration
    section "Step 3: Update Configuration"
    log "Setting rollout to ${ROLLOUT_PERCENT}% (100% Event-Driven!)..."
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
    warn "Note: 24h monitoring may take a while. You can Ctrl+C and monitor manually if needed."
    echo ""

    # Auto-monitor with rollback on failure
    if ! "$SCRIPT_DIR/monitor.sh" --duration="$MONITORING_DURATION" --threshold=0.95 --auto-rollback; then
        error "Monitoring detected issues. Rollback was executed."
        exit 1
    fi

    # Step 7: SUCCESS! 🎉
    celebrate_success
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
    log "  EVENT_DRIVEN_ROLLOUT_PERCENT=$percent (100%!)"
}

celebrate_success() {
    section "🎉 ROLLOUT COMPLETE! 🎉"

    cat << 'EOF'

    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║    🎉🎉🎉 Event-Driven Architecture Fully Deployed! 🎉🎉🎉   ║
    ║                                                          ║
    ║    100% of traffic is now using Event-Driven mode       ║
    ║                                                          ║
    ║    Congratulations! You've successfully completed       ║
    ║    the phased rollout of Event-Driven Architecture!     ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝

EOF

    echo ""
    log "📊 Monitoring Dashboard: http://localhost:3001/d/ab-testing"
    log "📈 Prometheus Metrics: http://localhost:9090"
    log "📝 Documentation: docs/EVENT_DRIVEN_PRODUCTION_ROLLOUT.md"
    echo ""
    log "Post-Rollout Tasks:"
    log "  ✅ Phase 1 (10%) - Completed"
    log "  ✅ Phase 2 (50%) - Completed"
    log "  ✅ Phase 3 (100%) - Completed"
    echo ""
    log "Next Steps:"
    log "  1. Continue monitoring metrics for anomalies"
    log "  2. Review performance improvements in dashboard"
    log "  3. Document lessons learned"
    log "  4. Plan removal of HTTP Sync fallback (future)"
    echo ""
    log "Rollback (if needed):"
    log "  ./scripts/rollback-event-driven.sh"
    echo ""
}

main "$@"
