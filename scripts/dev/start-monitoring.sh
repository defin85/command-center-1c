#!/bin/bash

##############################################################################
# Start Monitoring & Observability Services (Prometheus + Grafana + Jaeger)
# Usage: ./scripts/dev/start-monitoring.sh
#
# Supports two modes:
#   USE_DOCKER=true  (default) - Docker containers
#   USE_DOCKER=false           - Native systemd services (Arch Linux)
##############################################################################

set -euo pipefail

# Определение путей
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение библиотеки
source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"

# Загрузить переменные окружения для определения режима
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

print_header "Starting Monitoring & Observability"

if is_docker_mode; then
    ##########################################################################
    # Docker режим
    ##########################################################################
    log_info "Режим: Docker"

    # Check if docker is running
    if ! is_docker_running; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check if base network exists
    if ! docker network inspect cc1c-local-network > /dev/null 2>&1; then
        log_warning "Network cc1c-local-network not found. Creating..."
        docker network create cc1c-local-network
    fi

    # Start monitoring services
    log_step "Starting Prometheus, Grafana and Jaeger..."
    docker-compose -f docker-compose.local.monitoring.yml up -d

    # Wait for services to be ready
    echo ""
    log_info "Waiting for services to be ready..."
    sleep 5

    # Check Prometheus
    if check_health_endpoint "http://localhost:9090/-/healthy"; then
        print_status "success" "Prometheus is ready: http://localhost:9090"
    else
        print_status "warning" "Prometheus may not be ready yet. Check: docker logs cc1c-prometheus-local"
    fi

    # Check Grafana
    if check_health_endpoint "http://localhost:5000/api/health"; then
        print_status "success" "Grafana is ready: http://localhost:5000 (admin/admin)"
    else
        print_status "warning" "Grafana may not be ready yet. Check: docker logs cc1c-grafana-local"
    fi

    # Check Jaeger
    if check_health_endpoint "http://localhost:16686/"; then
        print_status "success" "Jaeger is ready: http://localhost:16686"
    else
        print_status "warning" "Jaeger may not be ready yet. Check: docker logs cc1c-jaeger-local"
    fi

    print_header "Monitoring & Observability Started!"
    echo ""
    echo "Prometheus:  http://localhost:9090"
    echo "Grafana:     http://localhost:5000 (admin/admin)"
    echo "Jaeger:      http://localhost:16686 (OpenTelemetry Tracing)"
    echo ""
    echo "OTLP Endpoints (for instrumentation):"
    echo "   gRPC: localhost:4317"
    echo "   HTTP: localhost:4318"
    echo ""
    echo "A/B Testing Dashboard should be auto-provisioned in Grafana"
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
else
    ##########################################################################
    # Native режим (systemd)
    ##########################################################################
    log_info "Режим: Native (systemd)"

    # Запуск нативного мониторинга
    if start_native_monitoring; then
        print_header "Monitoring & Observability Started!"
    else
        print_header "Monitoring & Observability Partially Started"
        log_warning "Некоторые сервисы не запустились (см. выше)"
    fi

    echo ""
    log_info "Проверка состояния сервисов:"
    check_native_monitoring_health

    echo ""
    echo "Prometheus:  http://localhost:9090"
    echo "Grafana:     http://localhost:3000 (admin/admin)"
    echo "Jaeger:      http://localhost:16686 (если установлен)"
    echo ""
    echo "Конфигурация Prometheus для нативного режима:"
    echo "  /etc/prometheus/prometheus.yml"
    echo "  Или используй: infrastructure/monitoring/prometheus/prometheus-native.yml"
    echo ""
    echo "To view logs:"
    echo "  journalctl -u prometheus -f"
    echo "  journalctl -u grafana -f"
    echo "  journalctl -u jaeger -f"
    echo ""
    echo "To stop:"
    echo "  ./scripts/dev/stop-monitoring.sh"
    echo "  OR"
    echo "  sudo systemctl stop prometheus grafana jaeger"
    echo ""

    # Подсказка для установки
    if ! command -v prometheus &>/dev/null; then
        log_warning "Prometheus не установлен. Установка:"
        echo "  pacman -S prometheus"
        echo "  sudo systemctl enable prometheus"
    fi

    if ! command -v grafana &>/dev/null && ! command -v grafana-server &>/dev/null; then
        log_warning "Grafana не установлен. Установка:"
        echo "  pacman -S grafana"
        echo "  sudo systemctl enable grafana"
    fi
fi
