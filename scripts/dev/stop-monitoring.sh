#!/bin/bash

##############################################################################
# Stop Monitoring & Observability Services (Prometheus + Grafana + Jaeger)
# Usage: ./scripts/dev/stop-monitoring.sh
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "========================================="
echo "  Stopping Monitoring & Observability"
echo "========================================="
echo ""

docker-compose -f docker-compose.local.monitoring.yml down

echo ""
echo "✅ Monitoring services stopped"
echo ""
echo "To preserve data: volumes are NOT deleted"
echo "To remove all data: docker volume rm cc1c-prometheus-local-data cc1c-grafana-local-data"
echo ""
