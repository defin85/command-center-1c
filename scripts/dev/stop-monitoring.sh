#!/bin/bash

##############################################################################
# Stop Monitoring & Observability Services (Prometheus + Grafana + Jaeger)
# Usage: ./scripts/dev/stop-monitoring.sh
##############################################################################

set -euo pipefail

# Определение путей
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение библиотеки
source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"

print_header "Stopping Monitoring & Observability"

docker-compose -f docker-compose.local.monitoring.yml down

echo ""
log_success "Monitoring services stopped"
echo ""
log_info "To preserve data: volumes are NOT deleted"
log_info "To remove all data: docker volume rm cc1c-prometheus-local-data cc1c-grafana-local-data"
echo ""
