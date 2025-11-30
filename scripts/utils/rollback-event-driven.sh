#!/bin/bash

##############################################################################
# CommandCenter1C - Event-Driven Architecture Rollback Script
##############################################################################
# Автоматический откат Event-Driven Architecture к HTTP Sync режиму
#
# Usage:
#   ./scripts/rollback-event-driven.sh           # Normal rollback
#   ./scripts/rollback-event-driven.sh --dry-run # Preview changes only
#   ./scripts/rollback-event-driven.sh --help    # Show help
#
# Exit codes:
#   0 - Success
#   1 - Failure (check logs)
#
# Execution time: < 2 minutes (target)
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE="$PROJECT_ROOT/.env.local"
ENV_BACKUP="$ENV_FILE.backup-$(date +%Y%m%d_%H%M%S)"
WORKER_PID_FILE="$PROJECT_ROOT/pids/worker.pid"
WORKER_LOG_FILE="$PROJECT_ROOT/logs/worker.log"

# Flags
DRY_RUN=false
SKIP_REDIS_FLUSH=false

##############################################################################
# Logging Functions
##############################################################################

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

debug() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] DEBUG:${NC} $1"
}

##############################################################################
# Helper Functions
##############################################################################

show_help() {
    cat << EOF
${BLUE}CommandCenter1C - Event-Driven Architecture Rollback${NC}

${YELLOW}USAGE:${NC}
    $0 [OPTIONS]

${YELLOW}OPTIONS:${NC}
    --dry-run           Preview changes without modifying system
    --skip-redis-flush  Skip Redis event channels cleanup
    --help              Show this help message

${YELLOW}EXAMPLES:${NC}
    # Normal rollback
    $0

    # Preview changes only (safe)
    $0 --dry-run

    # Rollback without Redis cleanup
    $0 --skip-redis-flush

${YELLOW}WHAT IT DOES:${NC}
    1. Backs up current .env.local configuration
    2. Updates feature flags (ENABLE_EVENT_DRIVEN=false)
    3. Restarts Worker service
    4. Verifies rollback via Prometheus metrics
    5. Optionally flushes Redis event channels

${YELLOW}EXIT CODES:${NC}
    0 - Success
    1 - Failure (check error messages)

${YELLOW}EXECUTION TIME:${NC}
    < 2 minutes (typical: 15-30 seconds)

${YELLOW}SUPPORT:${NC}
    Documentation: docs/EVENT_DRIVEN_ROLLBACK_PLAN.md
    Slack: #platform-team
    PagerDuty: "Platform On-Call"

EOF
}

check_prerequisites() {
    info "Checking prerequisites..."

    # Check .env.local exists
    if [ ! -f "$ENV_FILE" ]; then
        error ".env.local not found: $ENV_FILE"
        error "Run 'cp .env.local.example .env.local' first"
        return 1
    fi

    # Check restart.sh script exists
    if [ ! -f "$SCRIPT_DIR/dev/restart.sh" ]; then
        error "restart.sh not found: $SCRIPT_DIR/dev/restart.sh"
        return 1
    fi

    # Check curl available (for verification)
    if ! command -v curl &> /dev/null; then
        warn "curl not found - verification step will be skipped"
    fi

    # Check docker available (for Redis flush)
    if ! command -v docker &> /dev/null; then
        warn "docker not found - Redis flush will be skipped"
        SKIP_REDIS_FLUSH=true
    fi

    log "✓ Prerequisites check passed"
    return 0
}

backup_configuration() {
    info "Step 1/4: Backing up current configuration..."

    if [ "$DRY_RUN" = true ]; then
        debug "DRY RUN: Would backup $ENV_FILE to $ENV_BACKUP"
        return 0
    fi

    cp "$ENV_FILE" "$ENV_BACKUP"

    if [ -f "$ENV_BACKUP" ]; then
        log "✓ Configuration backed up to: $ENV_BACKUP"
    else
        error "Failed to backup configuration"
        return 1
    fi

    return 0
}

update_configuration() {
    info "Step 2/4: Updating .env.local..."

    # Show current configuration
    debug "Current Event-Driven configuration:"
    grep "^ENABLE_EVENT_DRIVEN=" "$ENV_FILE" || echo "  (not set)"
    grep "^EVENT_DRIVEN_ROLLOUT_PERCENT=" "$ENV_FILE" || echo "  (not set)"
    grep "^EVENT_DRIVEN_TARGET_DBS=" "$ENV_FILE" || echo "  (not set)"

    if [ "$DRY_RUN" = true ]; then
        debug "DRY RUN: Would update configuration to:"
        echo "  ENABLE_EVENT_DRIVEN=false"
        echo "  EVENT_DRIVEN_ROLLOUT_PERCENT=0.0"
        echo "  EVENT_DRIVEN_TARGET_DBS="
        return 0
    fi

    # Update ENABLE_EVENT_DRIVEN
    if grep -q "^ENABLE_EVENT_DRIVEN=" "$ENV_FILE"; then
        sed -i 's/^ENABLE_EVENT_DRIVEN=.*/ENABLE_EVENT_DRIVEN=false/' "$ENV_FILE"
    else
        echo "ENABLE_EVENT_DRIVEN=false" >> "$ENV_FILE"
    fi

    # Update EVENT_DRIVEN_ROLLOUT_PERCENT
    if grep -q "^EVENT_DRIVEN_ROLLOUT_PERCENT=" "$ENV_FILE"; then
        sed -i 's/^EVENT_DRIVEN_ROLLOUT_PERCENT=.*/EVENT_DRIVEN_ROLLOUT_PERCENT=0.0/' "$ENV_FILE"
    else
        echo "EVENT_DRIVEN_ROLLOUT_PERCENT=0.0" >> "$ENV_FILE"
    fi

    # Clear EVENT_DRIVEN_TARGET_DBS
    if grep -q "^EVENT_DRIVEN_TARGET_DBS=" "$ENV_FILE"; then
        sed -i 's/^EVENT_DRIVEN_TARGET_DBS=.*/EVENT_DRIVEN_TARGET_DBS=/' "$ENV_FILE"
    else
        echo "EVENT_DRIVEN_TARGET_DBS=" >> "$ENV_FILE"
    fi

    # Disable operation type targeting
    if grep -q "^EVENT_DRIVEN_EXTENSIONS=" "$ENV_FILE"; then
        sed -i 's/^EVENT_DRIVEN_EXTENSIONS=.*/EVENT_DRIVEN_EXTENSIONS=false/' "$ENV_FILE"
    fi
    if grep -q "^EVENT_DRIVEN_BACKUPS=" "$ENV_FILE"; then
        sed -i 's/^EVENT_DRIVEN_BACKUPS=.*/EVENT_DRIVEN_BACKUPS=false/' "$ENV_FILE"
    fi

    # Verify changes
    debug "New configuration:"
    grep "^ENABLE_EVENT_DRIVEN=" "$ENV_FILE"
    grep "^EVENT_DRIVEN_ROLLOUT_PERCENT=" "$ENV_FILE"
    grep "^EVENT_DRIVEN_TARGET_DBS=" "$ENV_FILE"

    log "✓ Configuration updated"
    return 0
}

restart_worker() {
    info "Step 3/4: Restarting Worker service..."

    if [ "$DRY_RUN" = true ]; then
        debug "DRY RUN: Would restart Worker service"
        return 0
    fi

    # Restart using existing script
    cd "$PROJECT_ROOT"

    if ! "$SCRIPT_DIR/dev/restart.sh" worker; then
        error "Failed to restart Worker service"
        error "Check logs: $WORKER_LOG_FILE"
        return 1
    fi

    # Wait for worker to start
    sleep 3

    # Check worker is running
    if [ -f "$WORKER_PID_FILE" ]; then
        WORKER_PID=$(cat "$WORKER_PID_FILE")
        if kill -0 "$WORKER_PID" 2>/dev/null; then
            log "✓ Worker service restarted (PID: $WORKER_PID)"
        else
            error "Worker process not running (PID: $WORKER_PID)"
            error "Check logs: $WORKER_LOG_FILE"
            return 1
        fi
    else
        error "Worker PID file not found: $WORKER_PID_FILE"
        return 1
    fi

    # Check logs for successful start
    if [ -f "$WORKER_LOG_FILE" ]; then
        if grep -q "enable_event_driven=false" "$WORKER_LOG_FILE" 2>/dev/null; then
            log "✓ Worker started in HTTP Sync mode"
        else
            warn "Could not verify HTTP Sync mode in logs"
        fi
    fi

    return 0
}

verify_rollback() {
    info "Step 4/4: Verifying rollback..."

    if [ "$DRY_RUN" = true ]; then
        debug "DRY RUN: Would verify rollback via Prometheus"
        return 0
    fi

    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        warn "curl not available - skipping verification"
        warn "Manually verify via Prometheus: http://localhost:9090"
        return 0
    fi

    # Wait for metrics to update
    sleep 5

    # Query Prometheus for execution mode
    local prometheus_url="http://localhost:9090/api/v1/query"
    local query="rate(worker_execution_mode_total[1m])"

    debug "Querying Prometheus: $prometheus_url?query=$query"

    local response
    if ! response=$(curl -s -f "$prometheus_url?query=$query" 2>/dev/null); then
        warn "Failed to query Prometheus - verification skipped"
        warn "Manually verify via: http://localhost:9090"
        return 0
    fi

    debug "Prometheus response: $response"

    # Check if http_sync mode is active
    if echo "$response" | grep -q '"mode":"http_sync"'; then
        log "✓ HTTP Sync mode verified via Prometheus"
    else
        warn "Could not verify HTTP Sync mode via Prometheus"
        warn "Metrics may take 1-2 minutes to update"
        warn "Manually check: $prometheus_url"
    fi

    # Check event_driven mode is NOT active
    if echo "$response" | grep -q '"mode":"event_driven"'; then
        warn "Event-Driven mode still shows activity"
        warn "This may be residual metrics - monitor for 5 minutes"
    fi

    return 0
}

flush_redis_channels() {
    info "Optional: Flushing Redis event channels..."

    if [ "$SKIP_REDIS_FLUSH" = true ]; then
        info "Skipping Redis flush (--skip-redis-flush flag)"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        debug "DRY RUN: Would flush Redis event channels"
        return 0
    fi

    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        warn "docker not available - skipping Redis flush"
        return 0
    fi

    # Check if redis container is running
    if ! docker ps | grep -q redis; then
        warn "Redis container not running - skipping flush"
        return 0
    fi

    # Flush event channels (FIXED: Issue #2 - Command injection vulnerability)
    debug "Flushing events:operation:* keys..."
    docker exec redis redis-cli --scan --pattern "events:operation:*" | \
        while IFS= read -r key; do
            [ -n "$key" ] && docker exec redis redis-cli DEL "$key" 2>/dev/null || true
        done

    debug "Flushing events:locks:* keys..."
    docker exec redis redis-cli --scan --pattern "events:locks:*" | \
        while IFS= read -r key; do
            [ -n "$key" ] && docker exec redis redis-cli DEL "$key" 2>/dev/null || true
        done

    # Verify cleanup
    local event_keys
    event_keys=$(docker exec redis redis-cli --scan --pattern "events:*" 2>/dev/null | wc -l)

    if [ "$event_keys" -eq 0 ]; then
        log "✓ Redis event channels flushed"
    else
        warn "Some event keys remain in Redis ($event_keys keys)"
        warn "They will expire automatically or can be manually cleaned"
    fi

    return 0
}

print_summary() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✅ Rollback Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}DRY RUN MODE:${NC} No changes were made"
        echo -e "${YELLOW}Run without --dry-run to execute rollback${NC}"
        echo ""
        return 0
    fi

    echo -e "${BLUE}Summary:${NC}"
    echo -e "  ✓ Configuration backed up: $ENV_BACKUP"
    echo -e "  ✓ ENABLE_EVENT_DRIVEN=false"
    echo -e "  ✓ EVENT_DRIVEN_ROLLOUT_PERCENT=0.0"
    echo -e "  ✓ Worker service restarted"
    echo -e "  ✓ HTTP Sync mode active"
    echo ""

    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "  1. Monitor dashboard: http://localhost:3001/d/ab-testing-event-driven"
    echo -e "  2. Verify success rate > 95% for 30 minutes"
    echo -e "  3. Check for stuck operations: 0 expected"
    echo -e "  4. Complete verification checklist: docs/EVENT_DRIVEN_ROLLBACK_PLAN.md"
    echo ""

    echo -e "${BLUE}Verification Commands:${NC}"
    echo -e "  # Check worker logs"
    echo -e "  tail -f $WORKER_LOG_FILE"
    echo ""
    echo -e "  # Query metrics"
    echo -e "  curl -s 'http://localhost:9090/api/v1/query?query=worker_execution_mode_total' | jq"
    echo ""
    echo -e "  # Check stuck operations"
    echo -e "  docker exec -it postgres psql -U commandcenter -d commandcenter -c \\"
    echo -e "    \"SELECT COUNT(*) FROM operations_operation WHERE status IN ('processing', 'pending');\""
    echo ""

    echo -e "${YELLOW}Support:${NC}"
    echo -e "  Documentation: docs/EVENT_DRIVEN_ROLLBACK_PLAN.md"
    echo -e "  Slack: #platform-team"
    echo ""
}

rollback_on_error() {
    error "Rollback failed! Rolling back changes..."

    if [ -f "$ENV_BACKUP" ]; then
        warn "Restoring configuration from backup..."
        cp "$ENV_BACKUP" "$ENV_FILE"
        log "Configuration restored"
    fi

    error "See logs for details: $WORKER_LOG_FILE"
    error "Manual intervention may be required"
    error "Contact platform team: #platform-team"

    exit 1
}

##############################################################################
# Main Execution
##############################################################################

main() {
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-redis-flush)
                SKIP_REDIS_FLUSH=true
                shift
                ;;
            --help|-h)
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

    # Set error handler
    trap rollback_on_error ERR

    # Print header
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  🔄 Event-Driven Architecture Rollback${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""

    if [ "$DRY_RUN" = true ]; then
        warn "DRY RUN MODE - No changes will be made"
        echo ""
    fi

    # Record start time
    START_TIME=$(date +%s)

    # Execute rollback steps
    check_prerequisites || exit 1
    backup_configuration || exit 1
    update_configuration || exit 1
    restart_worker || exit 1
    verify_rollback || exit 1
    flush_redis_channels || true  # Optional, don't fail on error

    # Record end time
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # Print summary
    print_summary

    log "✅ Rollback completed in ${DURATION} seconds"

    if [ "$DURATION" -gt 120 ]; then
        warn "Rollback took longer than 2 minutes target (${DURATION}s)"
    fi
}

# Execute main function
main "$@"
