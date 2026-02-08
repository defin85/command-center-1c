#!/bin/bash

##############################################################################
# Sync frontend/.env.local from root .env.local (CC1C_BASE_HOST)
##############################################################################
# Usage:
#   ./scripts/dev/sync-frontend-env.sh
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"
load_env_file

FRONTEND_ENV="$PROJECT_ROOT/frontend/.env.local"
BASE_HOST="${CC1C_BASE_HOST:-localhost}"

extra_lines=""
if [[ -f "$FRONTEND_ENV" ]]; then
    # Keep any user-provided overrides (e.g., VITE_API_URL) intact.
    extra_lines=$(tr -d '\000' < "$FRONTEND_ENV" | grep -a -v -E '^(VITE_BASE_HOST)=' || true)
fi

cat > "$FRONTEND_ENV" <<EOF
# Frontend Environment Variables (Local Development)
# Auto-synced from root .env.local (CC1C_BASE_HOST)

VITE_BASE_HOST=${BASE_HOST}

# По умолчанию Frontend использует same-origin:
# - REST: /api/* (Vite proxy -> API Gateway)
# - WS:   /ws/*  (Vite proxy -> API Gateway)
#
# Для prod-like режима (прямые запросы в API Gateway) можно раскомментировать:
# VITE_API_URL=http://${BASE_HOST}:8180/api/v2
# VITE_WS_HOST=${BASE_HOST}:8180
EOF

if [[ -n "$extra_lines" ]]; then
    printf "\n%s\n" "$extra_lines" >> "$FRONTEND_ENV"
fi

log_success "Synced frontend env: $FRONTEND_ENV"
