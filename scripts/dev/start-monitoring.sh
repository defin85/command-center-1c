#!/bin/bash

##############################################################################
# Start Monitoring & Observability Services (Prometheus + Grafana + Jaeger)
# Usage: ./scripts/dev/start-monitoring.sh
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "========================================="
echo "  Starting Monitoring & Observability"
echo "========================================="
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if base network exists
if ! docker network inspect cc1c-local-network > /dev/null 2>&1; then
    echo "⚠️  Network cc1c-local-network not found. Creating..."
    docker network create cc1c-local-network
fi

# Start monitoring services
echo "🚀 Starting Prometheus, Grafana and Jaeger..."
docker-compose -f docker-compose.local.monitoring.yml up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check Prometheus
if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is ready: http://localhost:9090"
else
    echo "⚠️  Prometheus may not be ready yet. Check: docker logs cc1c-prometheus-local"
fi

# Check Grafana
if curl -sf http://localhost:5000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is ready: http://localhost:5000 (admin/admin)"
else
    echo "⚠️  Grafana may not be ready yet. Check: docker logs cc1c-grafana-local"
fi

# Check Jaeger
if curl -sf http://localhost:16686/ > /dev/null 2>&1; then
    echo "✅ Jaeger is ready: http://localhost:16686"
else
    echo "⚠️  Jaeger may not be ready yet. Check: docker logs cc1c-jaeger-local"
fi

echo ""
echo "========================================="
echo "  Monitoring & Observability Started!"
echo "========================================="
echo ""
echo "📊 Prometheus:  http://localhost:9090"
echo "📈 Grafana:     http://localhost:5000 (admin/admin)"
echo "🔍 Jaeger:      http://localhost:16686 (OpenTelemetry Tracing)"
echo ""
echo "🔌 OTLP Endpoints (for instrumentation):"
echo "   gRPC: localhost:4317"
echo "   HTTP: localhost:4318"
echo ""
echo "🎯 A/B Testing Dashboard should be auto-provisioned in Grafana"
echo ""
echo "To view logs:"
echo "  docker logs -f cc1c-prometheus-local"
echo "  docker logs -f cc1c-grafana-local"
echo "  docker logs -f cc1c-jaeger-local"
echo ""
echo "To stop:"
echo "  ./scripts/dev/stop-monitoring.sh"
echo "  OR"
echo "  docker-compose -f docker-compose.local.monitoring.yml down"
echo ""
