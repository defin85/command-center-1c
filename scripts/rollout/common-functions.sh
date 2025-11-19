#!/bin/bash
# scripts/rollout/common-functions.sh
# Shared utility functions for rollout scripts

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
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
    if [ "${DEBUG:-false}" == "true" ]; then
        echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] DEBUG:${NC} $1"
    fi
}

# Print section header
section() {
    echo ""
    echo -e "${MAGENTA}========================================${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}========================================${NC}"
    echo ""
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Ensure required commands are available
ensure_commands() {
    local missing=()
    for cmd in "$@"; do
        if ! command_exists "$cmd"; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Missing required commands: ${missing[*]}"
        return 1
    fi
    return 0
}

# Wait for user confirmation
confirm() {
    local prompt="$1"
    local default="${2:-n}"

    if [ "$default" == "y" ]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$prompt" response
    response=${response:-$default}

    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Check if service is healthy
check_service_health() {
    local name="$1"
    local url="$2"

    if curl -sf "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check if PostgreSQL is ready
check_postgres() {
    docker exec postgres pg_isready > /dev/null 2>&1
}

# Check if Redis is ready
check_redis() {
    docker exec redis redis-cli ping > /dev/null 2>&1
}

# Parse duration string (4h, 30m, 2h30m) to seconds
duration_to_seconds() {
    local duration="$1"

    # Parse duration (e.g., 4h, 30m, 2h30m, 1d)
    if [[ "$duration" =~ ^([0-9]+)d$ ]]; then
        echo $((${BASH_REMATCH[1]} * 86400))
    elif [[ "$duration" =~ ^([0-9]+)h$ ]]; then
        echo $((${BASH_REMATCH[1]} * 3600))
    elif [[ "$duration" =~ ^([0-9]+)m$ ]]; then
        echo $((${BASH_REMATCH[1]} * 60))
    elif [[ "$duration" =~ ^([0-9]+)s$ ]]; then
        echo ${BASH_REMATCH[1]}
    elif [[ "$duration" =~ ^([0-9]+)h([0-9]+)m$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 3600 + ${BASH_REMATCH[2]} * 60 ))
    elif [[ "$duration" =~ ^([0-9]+)$ ]]; then
        # Pure number - assume seconds
        echo $duration
    else
        error "Invalid duration format: $duration"
        return 1
    fi
}

# Format seconds to human-readable duration
seconds_to_duration() {
    local seconds=$1
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))

    local result=""
    [ $days -gt 0 ] && result="${days}d "
    [ $hours -gt 0 ] && result="${result}${hours}h "
    [ $minutes -gt 0 ] && result="${result}${minutes}m "
    [ $secs -gt 0 ] && result="${result}${secs}s"

    echo "${result:-0s}"
}

# Query Prometheus
query_prometheus() {
    local query="$1"
    local result

    result=$(curl -sf "http://localhost:9090/api/v1/query?query=$(printf '%s' "$query" | jq -sRr @uri)" 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo "0"
        return 1
    fi

    # Extract value from response
    echo "$result" | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0"
}

# Compare floats (bash doesn't support float comparison natively)
float_gt() {
    awk -v n1="$1" -v n2="$2" 'BEGIN {print (n1 > n2)}'
}

float_lt() {
    awk -v n1="$1" -v n2="$2" 'BEGIN {print (n1 < n2)}'
}

float_ge() {
    awk -v n1="$1" -v n2="$2" 'BEGIN {print (n1 >= n2)}'
}

float_le() {
    awk -v n1="$1" -v n2="$2" 'BEGIN {print (n1 <= n2)}'
}

# Format float as percentage
format_percent() {
    local value="$1"
    awk -v val="$value" 'BEGIN {printf "%.2f%%", val * 100}'
}

# Create backup of file
backup_file() {
    local file="$1"
    local backup="${file}.backup.$(date +%s)"

    if [ -f "$file" ]; then
        cp "$file" "$backup"
        log "Backup created: $backup"
    fi
}

# Restore file from backup
restore_file() {
    local file="$1"
    local backup="$2"

    if [ -f "$backup" ]; then
        cp "$backup" "$file"
        log "Restored from backup: $backup"
    else
        error "Backup file not found: $backup"
        return 1
    fi
}

# Update .env.local variable
update_env_var() {
    local key="$1"
    local value="$2"
    local env_file="${3:-$PROJECT_ROOT/.env.local}"

    if [ ! -f "$env_file" ]; then
        error "Environment file not found: $env_file"
        return 1
    fi

    # Check if variable exists
    if grep -q "^${key}=" "$env_file"; then
        # Update existing
        sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
    else
        # Append new
        echo "${key}=${value}" >> "$env_file"
    fi

    debug "Updated $key=$value in $env_file"
}

# Get .env.local variable
get_env_var() {
    local key="$1"
    local env_file="${2:-$PROJECT_ROOT/.env.local}"

    if [ ! -f "$env_file" ]; then
        echo ""
        return 1
    fi

    grep "^${key}=" "$env_file" | cut -d'=' -f2- | tr -d '"' | tr -d "'"
}

# Print success banner
print_success() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                          ║${NC}"
    echo -e "${GREEN}║                    ✅ SUCCESS! ✅                         ║${NC}"
    echo -e "${GREEN}║                                                          ║${NC}"
    echo -e "${GREEN}║  $1${NC}"
    echo -e "${GREEN}║                                                          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print error banner
print_error() {
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                          ║${NC}"
    echo -e "${RED}║                    ❌ FAILURE ❌                          ║${NC}"
    echo -e "${RED}║                                                          ║${NC}"
    echo -e "${RED}║  $1${NC}"
    echo -e "${RED}║                                                          ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Update rollout configuration (ENABLE_EVENT_DRIVEN and ROLLOUT_PERCENT)
# Usage: update_rollout_config <percent>
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

# Execute rollout phase with standard checks and monitoring
# Usage: execute_phase <phase_number> <rollout_percent> <monitoring_duration>
execute_phase() {
    local phase_number="$1"
    local rollout_percent="$2"
    local monitoring_duration="$3"

    log "🚀 Phase $phase_number: Rollout to ${rollout_percent}%"
    log "=========================================="

    # Pre-flight checks
    log "📋 Step 1/5: Running pre-flight checks..."
    if ! "$SCRIPT_DIR/preflight-checks.sh"; then
        error "Pre-flight checks failed. Aborting rollout."
        return 1
    fi
    log "✅ Pre-flight checks passed"

    # Check previous phase (if not Phase 1)
    if [ "$phase_number" -gt 1 ]; then
        log "📊 Step 2/5: Checking Phase $(($phase_number - 1)) metrics..."
        if ! "$SCRIPT_DIR/check-metrics.sh" --phase=$(($phase_number - 1)); then
            error "Previous phase metrics not meeting criteria. Aborting."
            return 1
        fi
        log "✅ Previous phase metrics acceptable"
    else
        log "ℹ️  Step 2/5: Skipped (Phase 1 has no previous phase)"
    fi

    # User confirmation
    log "⚠️  Step 3/5: Confirmation required"
    echo ""
    echo "About to rollout Phase $phase_number (${rollout_percent}%)"
    echo "Monitoring duration: $monitoring_duration"
    echo ""
    read -p "Proceed with rollout? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        warn "Rollout cancelled by user"
        return 1
    fi

    # Update configuration
    log "🔧 Step 4/5: Updating configuration to ${rollout_percent}%..."
    update_rollout_config "$rollout_percent"
    log "✅ Configuration updated"

    # Deploy
    log "🚀 Step 4.5/5: Deploying (restarting Worker)..."
    "$PROJECT_ROOT/scripts/dev/restart.sh" worker
    log "✅ Worker restarted"

    # Monitor
    log "📊 Step 5/5: Starting monitoring (${monitoring_duration})..."
    log "Dashboard: http://localhost:3001/d/rollout"
    log "Prometheus: http://localhost:9090"
    echo ""

    if ! "$SCRIPT_DIR/monitor.sh" --duration="$monitoring_duration" --threshold=0.95 --auto-rollback; then
        error "Monitoring detected issues. Rollback executed."
        return 1
    fi

    log "✅ Phase $phase_number completed successfully!"

    return 0
}
