#!/usr/bin/env bash
# Backup/restore rehearsal for OperationExposure big-bang cutover.
# Usage examples:
#   ./scripts/rollout/backup-restore-operation-exposure-cutover.sh --dry-run
#   ./scripts/rollout/backup-restore-operation-exposure-cutover.sh --backup-dir ./storage/cutover-backups

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DRY_RUN=false
RESTORE_CHECK=true
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.local.yml"
POSTGRES_SERVICE="postgres"
DB_NAME="commandcenter"
DB_USER="commandcenter"
BACKUP_DIR="$PROJECT_ROOT/storage/cutover-backups"
RESTORE_DB_CREATED=false

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

show_help() {
    cat <<EOF
OperationExposure cutover backup/restore rehearsal

USAGE:
  $0 [OPTIONS]

OPTIONS:
  --dry-run                  Show actions without changing data.
  --skip-restore-check       Create backup only, skip restore validation.
  --compose-file PATH        Docker Compose file (default: $COMPOSE_FILE)
  --postgres-service NAME    Compose service name (default: $POSTGRES_SERVICE)
  --db-name NAME             Database name (default: $DB_NAME)
  --db-user NAME             Database user (default: $DB_USER)
  --backup-dir PATH          Backup directory (default: $BACKUP_DIR)
  --help                     Show this help.

EXIT CODES:
  0 - success
  1 - failure
EOF
}

compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        docker compose -f "$COMPOSE_FILE" "$@"
        return
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose -f "$COMPOSE_FILE" "$@"
        return
    fi
    error "Neither 'docker compose' nor 'docker-compose' is available."
    exit 1
}

run() {
    if [ "$DRY_RUN" = true ]; then
        info "DRY RUN: $*"
        return 0
    fi
    eval "$@"
}

cleanup_restore_db() {
    if [ "$DRY_RUN" = true ]; then
        return 0
    fi
    if [ "$RESTORE_CHECK" = true ] && [ "$RESTORE_DB_CREATED" = true ] && [ -n "${RESTORE_DB_NAME:-}" ]; then
        info "Cleanup: drop temporary restore database ($RESTORE_DB_NAME)"
        compose_cmd exec -T "$POSTGRES_SERVICE" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$RESTORE_DB_NAME\";" >/dev/null || true
    fi
}

assert_table_exists() {
    local db_name="$1"
    local table_name="$2"
    local exists
    exists="$(
        compose_cmd exec -T "$POSTGRES_SERVICE" \
            psql -U "$DB_USER" "$db_name" -tA -c "SELECT to_regclass('public.${table_name}') IS NOT NULL;"
    )"
    if [ "$exists" != "t" ]; then
        error "Expected table '${table_name}' is missing in database '${db_name}'"
        return 1
    fi
    return 0
}

check_prerequisites() {
    info "Checking prerequisites..."
    command -v docker >/dev/null 2>&1 || {
        error "docker is not available"
        return 1
    }
    if [ ! -f "$COMPOSE_FILE" ]; then
        error "Compose file not found: $COMPOSE_FILE"
        return 1
    fi
    command -v gzip >/dev/null 2>&1 || {
        error "gzip is required"
        return 1
    }
    command -v sha256sum >/dev/null 2>&1 || {
        error "sha256sum is required"
        return 1
    }
    if [ "$DRY_RUN" = false ]; then
        local service_id
        service_id="$(compose_cmd ps -q "$POSTGRES_SERVICE" 2>/dev/null || true)"
        if [ -z "$service_id" ]; then
            error "Postgres service '$POSTGRES_SERVICE' is not running in $COMPOSE_FILE"
            return 1
        fi
    fi
    log "Prerequisites check passed"
    return 0
}

main() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                ;;
            --skip-restore-check)
                RESTORE_CHECK=false
                ;;
            --compose-file)
                COMPOSE_FILE="$2"
                shift
                ;;
            --postgres-service)
                POSTGRES_SERVICE="$2"
                shift
                ;;
            --db-name)
                DB_NAME="$2"
                shift
                ;;
            --db-user)
                DB_USER="$2"
                shift
                ;;
            --backup-dir)
                BACKUP_DIR="$2"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                error "Unknown argument: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done

    local ts backup_file backup_path checksum_file restore_db
    ts="$(date +%Y%m%d_%H%M%S)"
    backup_file="operation_exposure_cutover_${ts}.sql.gz"
    backup_path="$BACKUP_DIR/$backup_file"
    checksum_file="${backup_path}.sha256"
    restore_db="${DB_NAME}_restore_check_${ts}"
    RESTORE_DB_NAME="$restore_db"

    trap cleanup_restore_db EXIT

    info "Starting backup/restore rehearsal for OperationExposure cutover"
    info "compose_file=$COMPOSE_FILE service=$POSTGRES_SERVICE db=$DB_NAME user=$DB_USER"
    info "backup_path=$backup_path restore_check=$RESTORE_CHECK dry_run=$DRY_RUN"

    check_prerequisites

    run "mkdir -p \"$BACKUP_DIR\""

    info "Step 1/4: creating backup dump"
    run "compose_cmd exec -T \"$POSTGRES_SERVICE\" pg_dump -U \"$DB_USER\" \"$DB_NAME\" | gzip > \"$backup_path\""

    info "Step 2/4: creating checksum"
    run "sha256sum \"$backup_path\" > \"$checksum_file\""

    if [ "$RESTORE_CHECK" = true ]; then
        info "Step 3/4: restore validation to temporary database ($restore_db)"
        run "compose_cmd exec -T \"$POSTGRES_SERVICE\" psql -U \"$DB_USER\" -d postgres -c \"DROP DATABASE IF EXISTS \\\"$restore_db\\\";\""
        run "compose_cmd exec -T \"$POSTGRES_SERVICE\" psql -U \"$DB_USER\" -d postgres -c \"CREATE DATABASE \\\"$restore_db\\\";\""
        if [ "$DRY_RUN" = false ]; then
            RESTORE_DB_CREATED=true
        fi
        run "gunzip -c \"$backup_path\" | compose_cmd exec -T \"$POSTGRES_SERVICE\" psql -U \"$DB_USER\" \"$restore_db\""

        info "Step 4/4: basic restore smoke checks"
        if [ "$DRY_RUN" = true ]; then
            run "compose_cmd exec -T \"$POSTGRES_SERVICE\" psql -U \"$DB_USER\" \"$restore_db\" -c \"SELECT COUNT(*) AS operation_templates_count FROM operation_templates;\""
            run "compose_cmd exec -T \"$POSTGRES_SERVICE\" psql -U \"$DB_USER\" \"$restore_db\" -c \"SELECT COUNT(*) AS operation_exposures_count FROM operation_exposures;\""
            run "compose_cmd exec -T \"$POSTGRES_SERVICE\" psql -U \"$DB_USER\" \"$restore_db\" -c \"SELECT COUNT(*) AS batch_operations_count FROM batch_operations;\""
        else
            assert_table_exists "$restore_db" "operation_templates"
            assert_table_exists "$restore_db" "operation_exposures"
            assert_table_exists "$restore_db" "batch_operations"
            compose_cmd exec -T "$POSTGRES_SERVICE" psql -U "$DB_USER" "$restore_db" -c "SELECT COUNT(*) AS operation_templates_count FROM operation_templates;"
            compose_cmd exec -T "$POSTGRES_SERVICE" psql -U "$DB_USER" "$restore_db" -c "SELECT COUNT(*) AS operation_exposures_count FROM operation_exposures;"
            compose_cmd exec -T "$POSTGRES_SERVICE" psql -U "$DB_USER" "$restore_db" -c "SELECT COUNT(*) AS batch_operations_count FROM batch_operations;"
        fi
        cleanup_restore_db
        RESTORE_DB_CREATED=false
    else
        warn "Restore validation skipped (--skip-restore-check)"
    fi

    log "Backup/restore rehearsal finished"
    log "Backup: $backup_path"
    log "Checksum: $checksum_file"
}

main "$@"
